"""Background worker for domain evaluation jobs."""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
from datetime import datetime, timezone

from sqlalchemy.exc import ProgrammingError

from apps.api.ingest import ingest_domain_sync
from apps.api.services.domain_index_state import (
    compute_desired_index_version,
    ensure_ingested,
    is_index_up_to_date,
)
from apps.api.services.domain_ingest_jobs import (
    claim_domain_ingest_job,
    finish_domain_ingest_job as finish_ingest_job,
    get_domain_ingest_job,
    set_domain_ingest_job_running,
)
from apps.api.services.domain_jobs import (
    claim_domain_eval_job,
    enqueue_domain_eval_job_if_absent,
    finish_domain_eval_job,
    get_pending_or_running_job_id_for_domain,
)
from apps.api.services.domain_orchestration_jobs import (
    claim_domain_eval_orchestration_job,
    finish_domain_eval_orchestration_job,
    set_orchestration_back_to_pending,
)
from apps.api.services.domain_orchestrate_jobs import (
    claim_domain_orchestrate_job,
    finish_domain_orchestrate_job,
    get_domain_orchestrate_job,
    set_orchestrate_current_domain,
    update_orchestrate_progress,
)
from apps.api.services.eval_runner import run_eval_sync
from apps.api.services.repo import (
    get_domain_index_state,
    list_eval_domains,
    list_tenant_ids,
    set_scheduler_last_tick,
    upsert_domain_index_state,
)
from apps.api.services.domain_index_validation import count_ac_embeddings, count_sections

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("domain-worker")

_STOP = threading.Event()
_SCHEDULER_LOCK = threading.Lock()
_SCHEDULER_CYCLE = 0


def _worker_id() -> str:
    host = socket.gethostname()
    pid = os.getpid()
    return f"{host}:{pid}"


def _to_iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _on_signal(signum, _frame) -> None:
    logger.info("worker_signal signum=%s stopping=1", signum)
    _STOP.set()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes")


def _env_int_minutes(name: str, default: int = 5, minimum: int = 1) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        logger.warning("scheduler_config_invalid key=%s value=%s fallback=%s", name, raw, default)
        return default


def _job_domains(job: dict) -> list[str]:
    raw = job.get("domains") or []
    if raw:
        return [str(d).strip().lower() for d in raw if str(d).strip()]
    # "evaluate all monitored domains" fallback
    return list_eval_domains(job["tenant_id"])


def _truncate_error(msg: str, max_len: int = 500) -> str:
    """Short message for last_error; avoid storing huge tracebacks."""
    s = (msg or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def run_domain_ingest_job(job_id: str) -> None:
    """
    Run the ingest pipeline for a domain_ingest_job: mark RUNNING, update domain_index_state,
    run crawl/ingest/sections/embeddings (existing ingest_domain_sync), then mark DONE or FAILED.
    """
    job = get_domain_ingest_job(job_id)
    if job is None:
        logger.warning("ingest_job_not_found job_id=%s", job_id)
        return
    status = (job.get("status") or "").upper()
    if status not in ("PENDING", "RUNNING"):
        logger.info("ingest_job_skip job_id=%s tenant_id=%s domain=%s status=%s", job_id, job.get("tenant_id"), job.get("domain"), status)
        return
    tenant_id = job["tenant_id"]
    domain = job["domain"]
    ac = job.get("desired_ac_version_hash") or ""
    ec = job.get("desired_ec_version_hash") or ""
    crawl = job.get("desired_crawl_policy_version") or ""

    if status == "PENDING":
        set_domain_ingest_job_running(job_id)

    logger.info(
        "ingest_job_start job_id=%s tenant_id=%s domain=%s desired_ac=%s desired_ec=%s desired_crawl=%s",
        job_id,
        tenant_id,
        domain,
        ac,
        ec,
        crawl,
    )

    upsert_domain_index_state(
        tenant_id,
        domain,
        status="RUNNING",
        last_error=None,
    )

    try:
        ingest_domain_sync(tenant_id, domain)
    except Exception as exc:
        err_short = _truncate_error(str(exc))
        upsert_domain_index_state(
            tenant_id,
            domain,
            status="FAILED",
            last_error=err_short,
        )
        finish_ingest_job(
            job_id,
            status="FAILED",
            error_code=type(exc).__name__,
            error_message=err_short,
        )
        logger.warning(
            "ingest_job_failed job_id=%s tenant_id=%s domain=%s last_error=%s",
            job_id,
            tenant_id,
            domain,
            err_short,
        )
        return

    # Post-ingest validation: require sections > 0 and embeddings > 0 (domain-scoped counts)
    n_sections = count_sections(tenant_id, domain)
    n_ac = count_ac_embeddings(tenant_id, domain)
    if n_sections == 0 or n_ac == 0:
        upsert_domain_index_state(
            tenant_id,
            domain,
            status="FAILED",
            last_error="Empty index (sections or ac_embeddings is 0)",
            error_code="EMPTY_INDEX",
        )
        finish_ingest_job(
            job_id,
            status="FAILED",
            error_code="EMPTY_INDEX",
            error_message="Empty index (sections or ac_embeddings is 0)",
        )
        logger.warning(
            "ingest_job_empty_index job_id=%s tenant_id=%s domain=%s sections=%s ac_embeddings=%s",
            job_id,
            tenant_id,
            domain,
            n_sections,
            n_ac,
        )
        return

    desired_after = compute_desired_index_version(tenant_id, domain)
    now = datetime.now(timezone.utc)
    upsert_domain_index_state(
        tenant_id,
        domain,
        status="DONE",
        last_indexed_at=now,
        ac_version_hash=desired_after.get("ac_version_hash"),
        ec_version_hash=desired_after.get("ec_version_hash"),
        crawl_policy_version=desired_after.get("crawl_policy_version"),
        last_error=None,
        error_code=None,
    )
    finish_ingest_job(job_id, status="DONE")
    logger.info(
        "ingest_job_done job_id=%s tenant_id=%s domain=%s stored_ac=%s stored_ec=%s",
        job_id,
        tenant_id,
        domain,
        desired_after.get("ac_version_hash", ""),
        desired_after.get("ec_version_hash", ""),
    )


def _assert_domain_indexed_for_eval(
    tenant_id: str,
    domain: str,
) -> tuple[bool, str | None]:
    """
    2-phase check: domain must be DONE with hashes matching desired. No global counts.
    Returns (ok, error_message). If not ok, error_message explains missing/stale/failed/RUNNING/PENDING.
    """
    desired = compute_desired_index_version(tenant_id, domain)
    state = get_domain_index_state(tenant_id, domain)

    if is_index_up_to_date(state, desired):
        return True, None

    # Not indexed: build explanation for DOMAIN_NOT_INDEXED
    status = (state.get("status") or "").upper() if state else ""
    if not state:
        return False, f"domain {domain!r}: index state missing (not indexed yet)"
    if status == "PENDING":
        return False, f"domain {domain!r}: index PENDING (ingest queued, not run)"
    if status == "RUNNING":
        return False, f"domain {domain!r}: index RUNNING (ingest in progress)"
    if status == "FAILED":
        err = (state.get("last_error") or "unknown error")[:200]
        return False, f"domain {domain!r}: index FAILED ({err})"
    # status not DONE or hashes mismatch
    return False, f"domain {domain!r}: index not up to date (status={status!r}, hashes mismatch or stale)"


def _process_job(job: dict, worker_id: str) -> None:
    job_id = job["id"]
    tenant_id = job["tenant_id"]
    domains = _job_domains(job)
    domain_count = len(domains) if domains else 1
    started = datetime.now(timezone.utc)
    logger.info(
        "job_picked job_id=%s tenant_id=%s worker_id=%s domain_count=%s started_at=%s",
        job_id,
        tenant_id,
        worker_id,
        domain_count,
        _to_iso(job.get("started_at")) or started.isoformat(),
    )

    completed = 0
    last_run_id: str | None = None
    try:
        # 2-phase: assert all domains indexed before any /answer calls (no global counts)
        for domain in domains:
            ok, not_indexed_msg = _assert_domain_indexed_for_eval(tenant_id, domain)
            if not ok:
                logger.warning(
                    "eval_job_domain_not_indexed job_id=%s tenant_id=%s domain=%s message=%s",
                    job_id,
                    tenant_id,
                    domain,
                    not_indexed_msg,
                )
                finish_domain_eval_job(
                    job_id,
                    status="FAILED",
                    completed=0,
                    error_code="DOMAIN_NOT_INDEXED",
                    error_message=not_indexed_msg,
                )
                return
        # All domains indexed: run eval only (no ingest)
        if domains:
            for domain in domains:
                result = run_eval_sync(tenant_id, domain)
                if result.get("run_id"):
                    last_run_id = str(result["run_id"])
                if result.get("ok") is False:
                    raise RuntimeError(str(result.get("error") or f"evaluation failed for domain={domain}"))
                completed += 1
        else:
            result = run_eval_sync(tenant_id, None)
            completed = 1
            if result.get("run_id"):
                last_run_id = str(result["run_id"])
            if result.get("ok") is False:
                raise RuntimeError(str(result.get("error") or "evaluation failed"))

        duration = (datetime.now(timezone.utc) - started).total_seconds()
        finish_domain_eval_job(
            job_id,
            status="DONE",
            completed=max(completed, int(job.get("total") or completed or 1)),
            run_id=last_run_id,
        )
        logger.info(
            "job_finished job_id=%s tenant_id=%s status=DONE duration_sec=%.2f domain_count=%s completed=%s",
            job_id,
            tenant_id,
            duration,
            domain_count,
            completed,
        )
    except Exception as exc:
        duration = (datetime.now(timezone.utc) - started).total_seconds()
        finish_domain_eval_job(
            job_id,
            status="FAILED",
            completed=completed,
            error_message=str(exc),
            run_id=last_run_id,
        )
        logger.exception(
            "job_failed job_id=%s tenant_id=%s status=FAILED duration_sec=%.2f domain_count=%s completed=%s error=%s",
            job_id,
            tenant_id,
            duration,
            domain_count,
            completed,
            str(exc),
        )


def run_domain_orchestrate_job(job_id: str) -> None:
    """
    Way 1 orchestrate: for each domain sequentially: ensure_ingested -> run ingest inline if needed -> run eval.
    If ingest fails for a domain: mark orchestrate job FAILED with error_code DOMAIN_NOT_INDEXED and stop
    (no further domains processed). MVP: small domain count (~3).
    """
    job = get_domain_orchestrate_job(job_id)
    if job is None:
        logger.warning("orchestrate_job_not_found job_id=%s", job_id)
        return
    status = (job.get("status") or "").upper()
    if status != "RUNNING":
        logger.info("orchestrate_job_skip job_id=%s status=%s", job_id, status)
        return
    tenant_id = job["tenant_id"]
    domains = job.get("domains") or []
    if not domains:
        finish_domain_orchestrate_job(job_id, "DONE", completed_domains=0)
        return

    logger.info(
        "orchestrate_start job_id=%s tenant_id=%s domain_count=%s status=RUNNING",
        job_id,
        tenant_id,
        len(domains),
    )
    completed = 0
    for domain in domains:
        # a) ensure ingested (may enqueue or return existing ingest job); index_state set RUNNING/DONE/FAILED in run_domain_ingest_job
        result = ensure_ingested(tenant_id, domain, reason="orchestrate")
        raw_status = (result.get("status") or "").upper()
        ingest_job_id = result.get("ingest_job_id")

        # b) if not DONE, run ingest inline (same worker); ingest runner sets domain_index_state RUNNING then DONE/FAILED
        if raw_status != "DONE" and ingest_job_id:
            logger.info(
                "orchestrate_domain_indexing_start job_id=%s tenant_id=%s domain=%s ingest_job_id=%s",
                job_id,
                tenant_id,
                domain,
                ingest_job_id,
            )
            run_domain_ingest_job(ingest_job_id)
            ingest_after = get_domain_ingest_job(ingest_job_id)
            if ingest_after and (ingest_after.get("status") or "").upper() == "FAILED":
                logger.warning(
                    "orchestrate_domain_indexing_failed job_id=%s tenant_id=%s domain=%s",
                    job_id,
                    tenant_id,
                    domain,
                )
                err_msg = (ingest_after.get("error_message") or "ingest failed")[: 500]
                finish_domain_orchestrate_job(
                    job_id,
                    "FAILED",
                    completed_domains=completed,
                    error_code="DOMAIN_NOT_INDEXED",
                    error_message=f"domain {domain!r}: ingest failed ({err_msg})",
                )
                return
            logger.info(
                "orchestrate_domain_indexing_done job_id=%s tenant_id=%s domain=%s",
                job_id,
                tenant_id,
                domain,
            )

        # c) run eval for this domain; set current_domain so API/UI can show EVALUATING
        set_orchestrate_current_domain(job_id, domain)
        logger.info(
            "orchestrate_domain_eval_start job_id=%s tenant_id=%s domain=%s status=EVALUATING",
            job_id,
            tenant_id,
            domain,
        )
        try:
            run_eval_sync(tenant_id, domain)
        except Exception as exc:
            set_orchestrate_current_domain(job_id, None)
            err_short = _truncate_error(str(exc))
            finish_domain_orchestrate_job(
                job_id,
                "FAILED",
                completed_domains=completed,
                error_code="EVAL_FAILED",
                error_message=f"domain {domain!r}: {err_short}",
            )
            logger.warning(
                "orchestrate_eval_failed job_id=%s tenant_id=%s domain=%s error=%s",
                job_id,
                tenant_id,
                domain,
                err_short,
            )
            return
        set_orchestrate_current_domain(job_id, None)
        logger.info(
            "orchestrate_domain_eval_done job_id=%s tenant_id=%s domain=%s",
            job_id,
            tenant_id,
            domain,
        )
        completed += 1
        update_orchestrate_progress(job_id, completed)

    finish_domain_orchestrate_job(job_id, "DONE", completed_domains=completed)
    logger.info(
        "orchestrate_job_done job_id=%s tenant_id=%s domain_count=%s status=DONE",
        job_id,
        tenant_id,
        len(domains),
    )


def _process_orchestration_job(orch_job: dict) -> None:
    """Check if all domains are indexed; if so enqueue eval job and mark orchestration DONE, else set back to PENDING."""
    job_id = orch_job["id"]
    tenant_id = orch_job["tenant_id"]
    domains = orch_job.get("domains") or []
    desired_per_domain = orch_job.get("desired_hashes_per_domain") or {}
    if not domains:
        finish_domain_eval_orchestration_job(job_id, "DONE", eval_job_id=None)
        return
    all_ready = True
    for domain in domains:
        desired = desired_per_domain.get(domain) or {}
        state = get_domain_index_state(tenant_id, domain)
        if not is_index_up_to_date(state, desired):
            all_ready = False
            break
    if all_ready:
        eval_job, created = enqueue_domain_eval_job_if_absent(tenant_id, domains)
        finish_domain_eval_orchestration_job(job_id, "DONE", eval_job_id=eval_job["id"])
        logger.info(
            "orchestration_done job_id=%s tenant_id=%s eval_job_id=%s created=%s domain_count=%s",
            job_id,
            tenant_id,
            eval_job["id"],
            created,
            len(domains),
        )
    else:
        set_orchestration_back_to_pending(job_id)
        logger.debug(
            "orchestration_waiting job_id=%s tenant_id=%s domain_count=%s",
            job_id,
            tenant_id,
            len(domains),
        )


def _auto_eval_tick() -> None:
    """
    One tick of the scheduled auto-evaluation: for each tenant with monitored domains,
    enqueue one domain_eval_job for domains that are indexed and not already PENDING/RUNNING.
    Skips overlap if the previous tick is still running.
    """
    if not _SCHEDULER_LOCK.acquire(blocking=False):
        logger.info("scheduler_skip_overlap previous_cycle_still_running")
        return
    try:
        global _SCHEDULER_CYCLE
        _SCHEDULER_CYCLE += 1
        cycle_id = _SCHEDULER_CYCLE
        cycle_started = datetime.now(timezone.utc)
        enabled = _env_bool("AUTO_EVAL_ENABLED", default=False)
        if not enabled:
            logger.debug("scheduler_tick_skip_disabled cycle_id=%s", cycle_id)
            return
        interval_min = _env_int_minutes("AUTO_EVAL_INTERVAL_MINUTES", default=5, minimum=1)
        tenants_raw = (os.getenv("AUTO_EVAL_TENANTS") or "").strip()
        if tenants_raw:
            tenant_ids = [t.strip() for t in tenants_raw.split(",") if t.strip()]
        else:
            try:
                tenant_ids = list_tenant_ids()
            except ProgrammingError as exc:
                logger.warning("scheduler_db_not_ready error=%s", str(exc))
                return
        if not tenant_ids:
            logger.info("scheduler_tick cycle_id=%s tenant_count=0 reason=no_tenants", cycle_id)
            return
        logger.info(
            "scheduler_tick cycle_id=%s tenant_count=%s interval_minutes=%s",
            cycle_id,
            len(tenant_ids),
            interval_min,
        )
        total_queued = 0
        total_eligible = 0
        total_skipped_not_indexed = 0
        total_skipped_pending = 0
        for tenant_id in tenant_ids:
            try:
                domains = list_eval_domains(tenant_id)
            except Exception as exc:
                logger.warning(
                    "scheduler_tenant_error cycle_id=%s tenant_id=%s error=%s",
                    cycle_id,
                    tenant_id,
                    str(exc),
                )
                continue
            domains = list(dict.fromkeys([d.strip().lower() for d in domains if d and d.strip()]))
            if not domains:
                logger.info("scheduler_tenant cycle_id=%s tenant_id=%s domains_monitored=0", cycle_id, tenant_id)
                continue
            eligible: list[str] = []
            skipped_not_indexed: list[str] = []
            skipped_pending: list[str] = []
            for domain in domains:
                state = get_domain_index_state(tenant_id, domain)
                desired = compute_desired_index_version(tenant_id, domain)
                if not is_index_up_to_date(state, desired):
                    skipped_not_indexed.append(domain)
                    continue
                if get_pending_or_running_job_id_for_domain(tenant_id, domain):
                    skipped_pending.append(domain)
                    continue
                eligible.append(domain)
            if skipped_not_indexed:
                logger.info(
                    "scheduler_skipped_not_indexed cycle_id=%s tenant_id=%s count=%s domains=%s",
                    cycle_id,
                    tenant_id,
                    len(skipped_not_indexed),
                    skipped_not_indexed[:10],
                )
            if skipped_pending:
                logger.info(
                    "scheduler_skipped_pending cycle_id=%s tenant_id=%s count=%s domains=%s",
                    cycle_id,
                    tenant_id,
                    len(skipped_pending),
                    skipped_pending[:10],
                )
            total_skipped_not_indexed += len(skipped_not_indexed)
            total_skipped_pending += len(skipped_pending)
            if not eligible:
                logger.info(
                    "scheduler_tenant cycle_id=%s tenant_id=%s domains_monitored=%s eligible=0",
                    cycle_id,
                    tenant_id,
                    len(domains),
                )
                continue
            total_eligible += len(eligible)
            try:
                job, created = enqueue_domain_eval_job_if_absent(tenant_id, eligible)
                job_id = str(job["id"])
                if created:
                    total_queued += 1
                    logger.info(
                        "scheduler_jobs_queued cycle_id=%s tenant_id=%s eval_job_id=%s domain_count=%s domains=%s",
                        cycle_id,
                        tenant_id,
                        job_id,
                        len(eligible),
                        eligible[:15],
                    )
                else:
                    logger.info(
                        "scheduler_enqueue_dedup cycle_id=%s tenant_id=%s eval_job_id=%s domain_count=%s",
                        cycle_id,
                        tenant_id,
                        job_id,
                        len(eligible),
                    )
            except Exception as exc:
                logger.exception(
                    "scheduler_enqueue_failed cycle_id=%s tenant_id=%s domain_count=%s error=%s",
                    cycle_id,
                    tenant_id,
                    len(eligible),
                    str(exc),
                )
        duration_sec = (datetime.now(timezone.utc) - cycle_started).total_seconds()
        logger.info(
            "scheduler_tick_done cycle_id=%s tenant_count=%s eligible=%s skipped_not_indexed=%s skipped_pending=%s jobs_queued=%s duration_sec=%.2f",
            cycle_id,
            len(tenant_ids),
            total_eligible,
            total_skipped_not_indexed,
            total_skipped_pending,
            total_queued,
            duration_sec,
        )
        try:
            set_scheduler_last_tick()
        except Exception as exc:
            logger.debug("scheduler_state_update_skip cycle_id=%s error=%s", cycle_id, str(exc))
    finally:
        _SCHEDULER_LOCK.release()


def _scheduler_loop(interval_seconds: float) -> None:
    """Daemon thread: run _auto_eval_tick immediately, then every interval_seconds until _STOP."""
    while not _STOP.is_set():
        try:
            _auto_eval_tick()
        except Exception as exc:
            logger.exception("scheduler_tick_error error=%s", str(exc))
        if _STOP.wait(timeout=interval_seconds):
            break


def main() -> None:
    worker_id = os.getenv("WORKER_ID", _worker_id())
    poll_seconds = float(os.getenv("WORKER_POLL_SECONDS", "2"))
    poll_seconds = min(max(poll_seconds, 1.0), 3.0)
    concurrency = max(int(os.getenv("WORKER_CONCURRENCY", "1")), 1)
    lease_seconds = max(int(os.getenv("WORKER_LEASE_SECONDS", "1800")), 60)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    logger.info(
        "worker_start worker_id=%s poll_seconds=%.1f concurrency=%s lease_seconds=%s",
        worker_id,
        poll_seconds,
        concurrency,
        lease_seconds,
    )

    auto_eval_enabled = _env_bool("AUTO_EVAL_ENABLED", default=False)
    if auto_eval_enabled:
        interval_min = _env_int_minutes("AUTO_EVAL_INTERVAL_MINUTES", default=5, minimum=1)
        interval_seconds = float(interval_min * 60)
        scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(interval_seconds,),
            name="auto-eval-scheduler",
            daemon=True,
        )
        scheduler_thread.start()
        logger.info(
            "scheduler_started interval_minutes=%s interval_seconds=%.0f",
            interval_min,
            interval_seconds,
        )

    while not _STOP.is_set():
        picked = 0
        for _ in range(concurrency):
            if _STOP.is_set():
                break
            try:
                job = claim_domain_eval_job(worker_id=worker_id, lease_seconds=lease_seconds)
            except ProgrammingError as exc:
                # Migration may still be running on API startup; worker retries until table exists.
                logger.warning("worker_db_not_ready error=%s", str(exc))
                time.sleep(poll_seconds)
                job = None
            if not job:
                break
            picked += 1
            _process_job(job, worker_id)
        # Also process one domain_ingest_job if no eval job was picked
        if picked == 0:
            try:
                ingest_job = claim_domain_ingest_job()
            except ProgrammingError:
                ingest_job = None
            if ingest_job:
                run_domain_ingest_job(ingest_job["id"])
                picked += 1
        # Then one orchestration job if still nothing picked
        if picked == 0:
            try:
                orch_job = claim_domain_eval_orchestration_job()
            except ProgrammingError:
                orch_job = None
            if orch_job:
                _process_orchestration_job(orch_job)
                picked += 1
        # Then one Way 1 orchestrate job (sequential ensure->ingest->eval per domain)
        if picked == 0:
            try:
                orch1_job = claim_domain_orchestrate_job()
            except ProgrammingError:
                orch1_job = None
            if orch1_job:
                run_domain_orchestrate_job(orch1_job["id"])
                picked += 1
        if picked == 0:
            time.sleep(poll_seconds)

    logger.info("worker_stop worker_id=%s", worker_id)


if __name__ == "__main__":
    main()
