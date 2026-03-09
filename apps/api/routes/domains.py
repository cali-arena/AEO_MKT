"""Tenant-scoped domain management and evaluation endpoints."""

from __future__ import annotations

import logging
import os
import re
from typing import Literal
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.api.schemas.eval import EvalMetricsRates
from apps.api.services.domain_index_state import ensure_ingested
from apps.api.services.domain_ingest_jobs import (
    clear_domain_ingest_jobs_for_tenant,
    get_domain_ingest_job,
    get_latest_ingest_job_statuses_for_tenant,
)
from apps.api.services.domain_jobs import (
    clear_domain_eval_jobs_for_tenant,
    enqueue_domain_eval_job,
    get_domain_eval_job,
)
from apps.api.services.domain_status import get_domains_with_status
from apps.api.services.domain_orchestration_jobs import (
    enqueue_domain_eval_orchestration_job,
    get_domain_eval_orchestration_job,
)
from apps.api.services.repo import (
    add_eval_domain,
    delete_domain_data,
    delete_invalid_eval_domains,
    get_domain_aggregates_from_eval_result,
    get_latest_eval_run,
    list_eval_domains,
)
from apps.api.services.tenant_context import TenantId

router = APIRouter()
logger = logging.getLogger(__name__)

BLOCKED_DOMAIN_PREFIXES = ("quote.", "app.", "secure.", "form.")


def _is_blocked_domain(domain: str) -> bool:
    """True if domain starts with a blocked prefix (quote/app/secure/form subdomains)."""
    d = (domain or "").strip().lower()
    return any(d.startswith(p) for p in BLOCKED_DOMAIN_PREFIXES)


def _reject_blocked_domains(normalized: list[str]) -> None:
    """Raise HTTP 400 if any domain is blocked; log each rejected domain."""
    for domain in normalized:
        if _is_blocked_domain(domain):
            logger.warning("Rejected unsupported domain: %s", domain)
            raise HTTPException(
                status_code=400,
                detail="Unsupported domain type (form/quote subdomains are not allowed)",
            )


_DOMAIN_REGEX = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.IGNORECASE,
)

class DomainsCreateBody(BaseModel):
    domains: list[str] = Field(default_factory=list)


class DomainsCreateResponse(BaseModel):
    status: str
    created: list[str]
    existing: list[str]


class DomainsEvaluateBody(BaseModel):
    domains: list[str] | None = None


class DesiredHashesRow(BaseModel):
    """Desired index version hashes for a domain (used in evaluate response)."""

    domain: str
    ac_version_hash: str
    ec_version_hash: str
    crawl_policy_version: str


class DomainEvaluateStateRow(BaseModel):
    """Per-domain initial state for evaluate response (UNINDEXED/INDEXING/DONE)."""

    domain: str
    state: Literal["UNINDEXED", "INDEXING", "DONE"]
    ingest_job_id: str | None = None


class DomainsEvaluateResponse(BaseModel):
    status: str
    message: str
    job_id: str
    status_url: str
    run_id: str | None = None
    started_domains: list[str]
    index_status: Literal["pending", "up_to_date", "running"] = "up_to_date"
    index_job_id: str | None = None
    eval_job_id: str | None = None
    desired_hashes: list[DesiredHashesRow] = Field(default_factory=list)
    orchestration_job_id: str | None = None
    domains_state: list[DomainEvaluateStateRow] = Field(default_factory=list)


class DomainRow(BaseModel):
    domain: str
    status: Literal["pending", "running", "done", "failed"]
    latest_rates: EvalMetricsRates | None = None
    total_results: int = 0
    refused_count: int = 0
    ok_count: int = 0
    last_run_id: str | None = None
    last_run_created_at: str | None = None
    failure_reason: str | None = None
    # From joined domain_index_state + latest eval job (get_domains_with_status)
    index_status: Literal["PENDING", "RUNNING", "DONE", "FAILED", "UNINDEXED"] | None = None
    last_indexed_at: str | None = None
    index_error: str | None = None
    eval_status: Literal["PENDING", "RUNNING", "DONE", "FAILED", "NONE"] | None = None
    orchestration_status: str | None = None
    ui_status: Literal["UNINDEXED", "INDEXING", "FAILED", "DONE", "EVALUATING"] | None = None
    # Backward compat
    last_error: str | None = None


class DomainsListResponse(BaseModel):
    tenant_id: str
    run_id: str | None
    domains: list[DomainRow]


class IngestJobStatusRow(BaseModel):
    """Latest ingest job status for one domain (for UI polling)."""

    job_id: str
    status: Literal["pending", "running", "done", "failed"]
    created_at: str | None
    started_at: str | None
    finished_at: str | None
    error_message: str | None = None
    error_code: str | None = None


class DomainsIngestStatusResponse(BaseModel):
    """Latest ingest job per domain for the tenant."""

    tenant_id: str
    domains: dict[str, IngestJobStatusRow] = Field(default_factory=dict)


class JobStatusResponse(BaseModel):
    job_id: str
    tenant_id: str
    status: Literal["pending", "running", "done", "failed"]
    total: int
    completed: int
    error_message: str | None = None
    error_code: str | None = None
    started_at: str
    finished_at: str | None = None


class DomainsClearHistoryResponse(BaseModel):
    status: str
    message: str
    deleted_eval_jobs: int
    deleted_ingest_jobs: int


class DomainsDeleteInvalidResponse(BaseModel):
    status: str
    removed: int
    message: str


class DomainDeletedResponse(BaseModel):
    ok: bool
    deleted_domain: str


def _enforce_tenant_match(path_tenant_id: str, auth_tenant_id: str) -> str:
    decoded = unquote(path_tenant_id or "").strip()
    if not decoded:
        raise HTTPException(status_code=400, detail="tenant_id is required in path")
    if decoded != auth_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant path does not match authenticated tenant")
    return decoded


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        raise ValueError("Domain is empty")
    raw = raw.replace("\\", "/")
    raw = re.sub(r"^[a-z][a-z0-9+.-]*://", "", raw)
    raw = raw.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    raw = raw.split("@")[-1]
    raw = raw.split(":", 1)[0]
    raw = raw.strip(".")
    if not raw or not _DOMAIN_REGEX.fullmatch(raw):
        raise ValueError(f"Invalid domain: {value}")
    return raw


def _normalize_domain_list(domains: list[str]) -> tuple[list[str], list[str]]:
    normalized: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for raw in domains:
        try:
            domain = _normalize_domain(raw)
        except ValueError:
            invalid.append(raw)
            continue
        if domain in seen:
            continue
        seen.add(domain)
        normalized.append(domain)
    return normalized, invalid


def _format_job_status(status: str) -> Literal["pending", "running", "done", "failed"]:
    s = (status or "").upper().strip()
    if s == "RUNNING":
        return "running"
    if s == "DONE":
        return "done"
    if s == "FAILED":
        return "failed"
    return "pending"


def _status_from_results(total_results: int, refused_count: int, ok_count: int) -> Literal["pending", "done", "failed"]:
    if total_results <= 0:
        return "pending"
    if refused_count >= total_results:
        return "failed"
    if ok_count > 0:
        return "done"
    return "pending"


def _ui_status_to_display_status(ui_status: str | None) -> Literal["pending", "running", "done", "failed"]:
    """Map ui_status to legacy status so UI cannot show DONE when index is missing/stale."""
    if not ui_status:
        return "pending"
    u = ui_status.upper()
    if u == "DONE":
        return "done"
    if u == "FAILED":
        return "failed"
    if u in ("INDEXING", "EVALUATING"):
        return "running"
    return "pending"


def _delete_domain_impl(tenant: str, domain_raw: str) -> DomainDeletedResponse:
    """Shared implementation for DELETE and POST delete; normalizes domain, deletes data, returns response."""
    try:
        domain_normalized = _normalize_domain(domain_raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        delete_domain_data(tenant, domain_normalized)
    except Exception as e:
        logger.exception("delete_domain failed tenant_id=%s domain=%s: %s", tenant, domain_normalized, e)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete domain and related data",
        )
    logger.info("domain_deleted tenant_id=%s domain=%s", tenant, domain_normalized)
    return DomainDeletedResponse(ok=True, deleted_domain=domain_normalized)


@router.delete(
    "/tenants/{tenant_id}/domains/{domain:path}",
    response_model=DomainDeletedResponse,
)
async def delete_domain(
    tenant_id: str,
    domain: str,
    auth_tenant_id: TenantId,
) -> DomainDeletedResponse:
    """Remove a domain from the monitored list and delete all related DB rows (eval_domain, domain_index_state, raw_page, jobs, sections, embeddings, evidence)."""
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    return _delete_domain_impl(tenant, domain)


@router.post(
    "/tenants/{tenant_id}/domains/{domain:path}/delete",
    response_model=DomainDeletedResponse,
)
async def post_delete_domain(
    tenant_id: str,
    domain: str,
    auth_tenant_id: TenantId,
) -> DomainDeletedResponse:
    """Same as DELETE .../domains/{domain}. POST is used when proxies block DELETE (e.g. 405 Method Not Allowed)."""
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    return _delete_domain_impl(tenant, domain)


@router.delete(
    "/tenants/{tenant_id}/domains",
    response_model=DomainsDeleteInvalidResponse,
)
async def delete_invalid_domains(
    tenant_id: str,
    auth_tenant_id: TenantId,
    invalid_only: bool = False,
) -> DomainsDeleteInvalidResponse:
    """Remove invalid domains (quote./app./secure./form.) from eval_domain. Requires invalid_only=true."""
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    if not invalid_only:
        raise HTTPException(
            status_code=400,
            detail="Only invalid_only=true is supported; removes quote/app/secure/form subdomains.",
        )
    removed = delete_invalid_eval_domains(tenant)
    logger.info("domains_delete_invalid tenant_id=%s removed=%s", tenant, removed)
    return DomainsDeleteInvalidResponse(
        status="ok",
        removed=removed,
        message=f"Removed {removed} invalid domain(s) from monitored list." if removed else "No invalid domains to remove.",
    )


@router.get("/tenants/{tenant_id}/domains", response_model=DomainsListResponse)
async def list_domains(tenant_id: str, auth_tenant_id: TenantId) -> DomainsListResponse:
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    run = get_latest_eval_run(tenant)
    run_id: str | None = str(run.id) if run is not None else None
    domains_with_status = get_domains_with_status(tenant)
    aggregates = get_domain_aggregates_from_eval_result(tenant)
    agg_by_domain = {a["domain"]: a for a in aggregates}
    for row in domains_with_status:
        d = row["domain"]
        if d not in agg_by_domain:
            agg_by_domain[d] = {
                "domain": d,
                "total_results": 0,
                "refused_count": 0,
                "ok_count": 0,
                "mention_rate": 0.0,
                "citation_rate": 0.0,
                "attribution_rate": 0.0,
                "hallucination_rate": 0.0,
                "refusal_reason_summary": None,
                "last_run_id": None,
                "last_created_at": None,
            }
    rows: list[DomainRow] = []
    pending_count = 0
    running_count = 0
    done_count = 0
    failed_count = 0
    for row in domains_with_status:
        domain = row["domain"]
        agg = agg_by_domain[domain]
        ui_status = row.get("ui_status")
        status = _ui_status_to_display_status(ui_status)
        if status == "pending":
            pending_count += 1
        elif status == "running":
            running_count += 1
        elif status == "failed":
            failed_count += 1
        else:
            done_count += 1
        latest_rates = EvalMetricsRates(
            mention_rate=agg["mention_rate"],
            citation_rate=agg["citation_rate"],
            attribution_rate=agg["attribution_rate"],
            hallucination_rate=agg["hallucination_rate"],
        )
        last_indexed = row.get("last_indexed_at")
        rows.append(
            DomainRow(
                domain=domain,
                status=status,
                latest_rates=latest_rates,
                total_results=int(agg.get("total_results") or 0),
                refused_count=int(agg.get("refused_count") or 0),
                ok_count=int(agg.get("ok_count") or 0),
                last_run_id=agg.get("last_run_id"),
                last_run_created_at=agg.get("last_created_at").isoformat() if agg.get("last_created_at") else None,
                failure_reason=(agg.get("refusal_reason_summary") if status == "failed" else None),
                index_status=row.get("index_status"),
                last_indexed_at=last_indexed.isoformat() if last_indexed else None,
                index_error=row.get("index_error"),
                eval_status=row.get("eval_status"),
                orchestration_status=row.get("orchestration_status"),
                ui_status=ui_status,
                last_error=row.get("index_error"),
            )
        )
    logger.info(
        "domains_list tenant_id=%s total=%s pending=%s running=%s done=%s failed=%s",
        tenant,
        len(rows),
        pending_count,
        running_count,
        done_count,
        failed_count,
    )
    return DomainsListResponse(tenant_id=tenant, run_id=run_id, domains=rows)


@router.get("/tenants/{tenant_id}/domains/ingest-status", response_model=DomainsIngestStatusResponse)
async def get_domains_ingest_status(
    tenant_id: str,
    auth_tenant_id: TenantId,
) -> DomainsIngestStatusResponse:
    """Return latest ingest job status per domain for the tenant (for UI polling)."""
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    raw = get_latest_ingest_job_statuses_for_tenant(tenant)
    domains: dict[str, IngestJobStatusRow] = {}
    for domain, job in raw.items():
        st = job.get("started_at") or job.get("created_at")
        ft = job.get("finished_at")
        domains[domain] = IngestJobStatusRow(
            job_id=str(job["id"]),
            status=_format_job_status(job.get("status") or ""),
            created_at=job["created_at"].isoformat() if job.get("created_at") else None,
            started_at=st.isoformat() if st else None,
            finished_at=ft.isoformat() if ft else None,
            error_message=job.get("error_message"),
            error_code=job.get("error_code"),
        )
    return DomainsIngestStatusResponse(tenant_id=tenant, domains=domains)


@router.post("/tenants/{tenant_id}/domains", response_model=DomainsCreateResponse)
async def create_domains(
    tenant_id: str,
    body: DomainsCreateBody,
    auth_tenant_id: TenantId,
) -> DomainsCreateResponse:
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    normalized, invalid = _normalize_domain_list(body.domains)
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid domain(s): {', '.join(invalid)}")
    if not normalized:
        raise HTTPException(status_code=400, detail="No valid domains provided")
    _reject_blocked_domains(normalized)
    delete_invalid_eval_domains(tenant)
    created: list[str] = []
    existing: list[str] = []
    for domain in normalized:
        if add_eval_domain(tenant, domain):
            created.append(domain)
        else:
            existing.append(domain)
    return DomainsCreateResponse(status="ok", created=created, existing=existing)


@router.post("/tenants/{tenant_id}/domains/clear-history", response_model=DomainsClearHistoryResponse)
async def clear_domains_history(
    request: Request,
    tenant_id: str,
    auth_tenant_id: TenantId,
) -> DomainsClearHistoryResponse:
    """Admin-only: delete all domain_eval_job and domain_ingest_job rows for this tenant.
    Requires X-Admin-Key header to match ADMIN_SECRET env. After success, client should refetch domains list."""
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    admin_secret = os.environ.get("ADMIN_SECRET")
    if not admin_secret:
        raise HTTPException(
            status_code=403,
            detail="Admin clear-history is disabled (ADMIN_SECRET not set)",
        )
    key = (request.headers.get("X-Admin-Key") or "").strip()
    if key != admin_secret:
        raise HTTPException(status_code=403, detail="Forbidden: admin key required")

    deleted_ingest = clear_domain_ingest_jobs_for_tenant(tenant)
    deleted_eval = clear_domain_eval_jobs_for_tenant(tenant)
    logger.info(
        "domains_clear_history tenant_id=%s deleted_eval_jobs=%s deleted_ingest_jobs=%s",
        tenant,
        deleted_eval,
        deleted_ingest,
    )
    return DomainsClearHistoryResponse(
        status="ok",
        message=f"Cleared job history: {deleted_eval} eval job(s) and {deleted_ingest} ingest job(s) removed.",
        deleted_eval_jobs=deleted_eval,
        deleted_ingest_jobs=deleted_ingest,
    )


@router.post("/tenants/{tenant_id}/domains/evaluate", response_model=DomainsEvaluateResponse, status_code=202)
async def evaluate_domains(
    tenant_id: str,
    body: DomainsEvaluateBody | None,
    auth_tenant_id: TenantId,
) -> DomainsEvaluateResponse:
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    delete_invalid_eval_domains(tenant)
    raw_domains = body.domains if body and body.domains is not None else None
    normalized: list[str] = []
    if raw_domains is not None:
        normalized, invalid = _normalize_domain_list(raw_domains)
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid domain(s): {', '.join(invalid)}")
        if not normalized:
            raise HTTPException(status_code=400, detail="No valid domains provided")
        _reject_blocked_domains(normalized)
        for domain in normalized:
            add_eval_domain(tenant, domain)
    else:
        normalized = list_eval_domains(tenant)

    # Ensure ingested per domain; when all indexed create domain_eval_job immediately, else enqueue orchestration
    desired_hashes: list[DesiredHashesRow] = []
    desired_hashes_per_domain: dict[str, dict[str, str]] = {}
    domains_state: list[DomainEvaluateStateRow] = []
    any_indexing = False
    all_done = True
    for domain in normalized:
        result = ensure_ingested(tenant, domain, reason="evaluate")
        desired = result.get("desired") or {}
        desired_hashes.append(
            DesiredHashesRow(
                domain=domain,
                ac_version_hash=desired.get("ac_version_hash", ""),
                ec_version_hash=desired.get("ec_version_hash", ""),
                crawl_policy_version=desired.get("crawl_policy_version", ""),
            )
        )
        desired_hashes_per_domain[domain] = {
            "ac_version_hash": desired.get("ac_version_hash", ""),
            "ec_version_hash": desired.get("ec_version_hash", ""),
            "crawl_policy_version": desired.get("crawl_policy_version", ""),
        }
        raw_status = (result.get("status") or "").upper()
        ingest_job_id = result.get("ingest_job_id")
        if raw_status == "DONE":
            domains_state.append(DomainEvaluateStateRow(domain=domain, state="DONE", ingest_job_id=None))
        elif raw_status in ("PENDING", "RUNNING"):
            any_indexing = True
            all_done = False
            domains_state.append(
                DomainEvaluateStateRow(domain=domain, state="INDEXING", ingest_job_id=str(ingest_job_id) if ingest_job_id else None)
            )
        else:
            all_done = False
            domains_state.append(
                DomainEvaluateStateRow(domain=domain, state="UNINDEXED", ingest_job_id=str(ingest_job_id) if ingest_job_id else None)
            )

    if all_done and normalized:
        # All domains indexed: create real domain_eval_job row so worker can run eval; return its id
        eval_job = enqueue_domain_eval_job(tenant, normalized)
        eval_job_id = str(eval_job["id"])
        job_id = eval_job_id
        status_url = f"/tenants/{tenant}/jobs/{eval_job_id}"
        logger.info(
            "domains_evaluate_eval_job_created tenant_id=%s eval_job_id=%s domain_count=%s domains=%s",
            tenant,
            eval_job_id,
            len(normalized),
            normalized,
        )
        return DomainsEvaluateResponse(
            status="started",
            message="Evaluation job created; worker will run evaluation shortly.",
            job_id=job_id,
            status_url=status_url,
            run_id=None,
            started_domains=normalized,
            index_status="up_to_date",
            index_job_id=None,
            eval_job_id=eval_job_id,
            desired_hashes=desired_hashes,
            orchestration_job_id=None,
            domains_state=domains_state,
        )

    orch = enqueue_domain_eval_orchestration_job(tenant, normalized, desired_hashes_per_domain)
    orchestration_job_id = orch["id"]
    job_id = orchestration_job_id
    status_url = f"/tenants/{tenant}/jobs/{orchestration_job_id}"
    index_status: Literal["pending", "up_to_date", "running"] = (
        "running" if any_indexing else "up_to_date"
    )
    first_ingest_id = next((s.ingest_job_id for s in domains_state if s.ingest_job_id), None)
    logger.info(
        "domains_evaluate_orchestration_enqueued tenant_id=%s orchestration_job_id=%s domain_count=%s all_done=%s",
        tenant,
        orchestration_job_id,
        len(normalized),
        all_done,
    )
    return DomainsEvaluateResponse(
        status="started",
        message="Orchestration started; evaluation will run when all domains are indexed."
        if not all_done
        else "Orchestration started; evaluation will run shortly.",
        job_id=job_id,
        status_url=status_url,
        run_id=None,
        started_domains=normalized,
        index_status=index_status,
        index_job_id=first_ingest_id,
        eval_job_id=None,
        desired_hashes=desired_hashes,
        orchestration_job_id=orchestration_job_id,
        domains_state=domains_state,
    )


@router.get("/tenants/{tenant_id}/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(tenant_id: str, job_id: str, auth_tenant_id: TenantId) -> JobStatusResponse:
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    state = get_domain_eval_job(tenant, job_id)
    if state is not None and str(state["tenant_id"]) == tenant:
        return JobStatusResponse(
            job_id=str(state["id"]),
            tenant_id=str(state["tenant_id"]),
            status=_format_job_status(state["status"]),
            total=int(state["total"]),
            completed=int(state["completed"]),
            error_message=state.get("error_message"),
            error_code=state.get("error_code"),
            started_at=(
                state["started_at"].isoformat()
                if state.get("started_at")
                else (state["created_at"].isoformat() if state.get("created_at") else "")
            ),
            finished_at=state["finished_at"].isoformat() if state.get("finished_at") else None,
        )
    # Try ingest job
    ingest = get_domain_ingest_job(job_id)
    if ingest is not None and str(ingest["tenant_id"]) == tenant:
        st = ingest.get("started_at") or ingest.get("created_at")
        started_at = st.isoformat() if st else ""
        finished_at = ingest.get("finished_at")
        return JobStatusResponse(
            job_id=str(ingest["id"]),
            tenant_id=str(ingest["tenant_id"]),
            status=_format_job_status(ingest["status"]),
            total=1,
            completed=1 if (ingest.get("status") or "").upper() == "DONE" else 0,
            error_message=ingest.get("error_message"),
            error_code=ingest.get("error_code"),
            started_at=started_at,
            finished_at=finished_at.isoformat() if finished_at else None,
        )
    # Try orchestration job
    orch = get_domain_eval_orchestration_job(job_id)
    if orch is not None and str(orch["tenant_id"]) == tenant:
        st = orch.get("created_at")
        started_at = st.isoformat() if st else ""
        return JobStatusResponse(
            job_id=str(orch["id"]),
            tenant_id=str(orch["tenant_id"]),
            status=_format_job_status(orch["status"]),
            total=len(orch.get("domains") or []),
            completed=1 if (orch.get("status") or "").upper() == "DONE" else 0,
            error_message=None,
            error_code=None,
            started_at=started_at,
            finished_at=orch["updated_at"].isoformat() if orch.get("updated_at") and (orch.get("status") or "").upper() == "DONE" else None,
        )
    raise HTTPException(status_code=404, detail="Job not found")
