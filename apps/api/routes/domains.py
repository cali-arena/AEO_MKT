"""Tenant-scoped domain management and evaluation endpoints."""

from __future__ import annotations

import logging
import re
from typing import Literal
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.schemas.eval import EvalMetricsRates
from apps.api.services.domain_jobs import (
    enqueue_domain_eval_job,
    get_domain_eval_job,
    get_latest_domain_job_statuses,
)
from apps.api.services.repo import add_eval_domain, get_latest_domain_eval_snapshots, get_latest_eval_run, list_eval_domains
from apps.api.services.tenant_context import TenantId

router = APIRouter()
logger = logging.getLogger(__name__)

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


class DomainsEvaluateResponse(BaseModel):
    status: str
    message: str
    job_id: str
    status_url: str
    run_id: str | None = None
    started_domains: list[str]


class DomainRow(BaseModel):
    domain: str
    status: Literal["pending", "running", "done", "failed"]
    latest_rates: EvalMetricsRates | None = None
    last_run_id: str | None = None
    last_run_created_at: str | None = None
    failure_reason: str | None = None


class DomainsListResponse(BaseModel):
    tenant_id: str
    run_id: str | None
    domains: list[DomainRow]


class JobStatusResponse(BaseModel):
    job_id: str
    tenant_id: str
    status: Literal["pending", "running", "done", "failed"]
    total: int
    completed: int
    error_message: str | None = None
    started_at: str
    finished_at: str | None = None


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


@router.get("/tenants/{tenant_id}/domains", response_model=DomainsListResponse)
async def list_domains(tenant_id: str, auth_tenant_id: TenantId) -> DomainsListResponse:
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    monitored = list_eval_domains(tenant)
    run = get_latest_eval_run(tenant)
    run_id: str | None = None
    if run is not None:
        run_id = str(run.id)
    snapshots = get_latest_domain_eval_snapshots(tenant)
    per_domain: dict[str, EvalMetricsRates] = {
        domain: EvalMetricsRates(
            mention_rate=float(snap["mention_rate"]),
            citation_rate=float(snap["citation_rate"]),
            attribution_rate=float(snap["attribution_rate"]),
            hallucination_rate=float(snap["hallucination_rate"]),
        )
        for domain, snap in snapshots.items()
    }
    domain_job_status = get_latest_domain_job_statuses(tenant)
    all_domains = sorted(set(monitored) | set(snapshots.keys()) | set(domain_job_status.keys()))
    rows: list[DomainRow] = []
    pending_count = 0
    running_count = 0
    done_count = 0
    failed_count = 0
    for domain in all_domains:
        rates = per_domain.get(domain)
        job_status = domain_job_status.get(domain)
        snap = snapshots.get(domain)
        if job_status == "RUNNING":
            status: Literal["pending", "running", "done", "failed"] = _format_job_status(job_status)
        elif snap is not None:
            status = "failed" if snap["status"] == "FAILED" else "done"
        elif job_status in {"FAILED", "PENDING"}:
            status = _format_job_status(job_status)
        elif rates is not None:
            status = "done"
        else:
            status = "pending"
        if status == "pending":
            pending_count += 1
        elif status == "running":
            running_count += 1
        elif status == "failed":
            failed_count += 1
        else:
            done_count += 1
        rows.append(
            DomainRow(
                domain=domain,
                status=status,
                latest_rates=rates,
                last_run_id=(str(snap["run_id"]) if snap else None),
                last_run_created_at=(
                    snap["run_created_at"].isoformat()
                    if snap and snap.get("run_created_at") is not None
                    else None
                ),
                failure_reason=(snap.get("refusal_reason_summary") if snap and snap["status"] == "FAILED" else None),
            )
        )
    logger.info(
        "domains_list tenant_id=%s domains=%s pending=%s running=%s done=%s failed=%s",
        tenant,
        len(rows),
        pending_count,
        running_count,
        done_count,
        failed_count,
    )
    return DomainsListResponse(tenant_id=tenant, run_id=run_id, domains=rows)


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
    created: list[str] = []
    existing: list[str] = []
    for domain in normalized:
        if add_eval_domain(tenant, domain):
            created.append(domain)
        else:
            existing.append(domain)
    return DomainsCreateResponse(status="ok", created=created, existing=existing)


@router.post("/tenants/{tenant_id}/domains/evaluate", response_model=DomainsEvaluateResponse, status_code=202)
async def evaluate_domains(
    tenant_id: str,
    body: DomainsEvaluateBody | None,
    auth_tenant_id: TenantId,
) -> DomainsEvaluateResponse:
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    raw_domains = body.domains if body and body.domains is not None else None
    normalized: list[str] = []
    if raw_domains is not None:
        normalized, invalid = _normalize_domain_list(raw_domains)
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid domain(s): {', '.join(invalid)}")
        if not normalized:
            raise HTTPException(status_code=400, detail="No valid domains provided")
        for domain in normalized:
            add_eval_domain(tenant, domain)
    else:
        normalized = list_eval_domains(tenant)
    state = enqueue_domain_eval_job(tenant, normalized)
    logger.info(
        "domains_evaluate_enqueued tenant_id=%s job_id=%s domain_count=%s",
        tenant,
        state["id"],
        len(normalized) if normalized else 0,
    )
    status_url = f"/tenants/{tenant}/jobs/{state['id']}"
    return DomainsEvaluateResponse(
        status="started",
        message="Evaluation started",
        job_id=state["id"],
        status_url=status_url,
        run_id=state.get("run_id"),
        started_domains=normalized,
    )


@router.get("/tenants/{tenant_id}/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(tenant_id: str, job_id: str, auth_tenant_id: TenantId) -> JobStatusResponse:
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    state = get_domain_eval_job(tenant, job_id)
    if state is None or str(state["tenant_id"]) != tenant:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=str(state["id"]),
        tenant_id=str(state["tenant_id"]),
        status=_format_job_status(state["status"]),
        total=int(state["total"]),
        completed=int(state["completed"]),
        error_message=state.get("error_message"),
        started_at=(
            state["started_at"].isoformat()
            if state.get("started_at")
            else (state["created_at"].isoformat() if state.get("created_at") else "")
        ),
        finished_at=state["finished_at"].isoformat() if state.get("finished_at") else None,
    )
