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

from apps.api.services.domain_jobs import claim_domain_eval_job, finish_domain_eval_job
from apps.api.services.eval_runner import run_eval_sync
from apps.api.services.repo import list_eval_domains

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("domain-worker")

_STOP = threading.Event()


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


def _job_domains(job: dict) -> list[str]:
    raw = job.get("domains") or []
    if raw:
        return [str(d).strip().lower() for d in raw if str(d).strip()]
    # "evaluate all monitored domains" fallback
    return list_eval_domains(job["tenant_id"])


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
        if domains:
            for domain in domains:
                result = run_eval_sync(tenant_id, domain)
                completed += 1
                if result.get("run_id"):
                    last_run_id = str(result["run_id"])
                if result.get("ok") is False:
                    raise RuntimeError(str(result.get("error") or f"evaluation failed for domain={domain}"))
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
        if picked == 0:
            time.sleep(poll_seconds)

    logger.info("worker_stop worker_id=%s", worker_id)


if __name__ == "__main__":
    main()
