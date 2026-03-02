"""Tenant-scoped domain management and evaluation endpoints."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import unquote
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.schemas.eval import EvalMetricsRates
from apps.api.services.eval_runner import run_eval_sync
from apps.api.services.repo import add_eval_domain, get_eval_metrics_for_run, get_latest_eval_run, list_eval_domains
from apps.api.services.tenant_context import TenantId

router = APIRouter()

_DOMAIN_REGEX = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.IGNORECASE,
)


@dataclass
class _JobState:
    job_id: str
    tenant_id: str
    domains: list[str]
    status: Literal["running", "completed", "failed"] = "running"
    total: int = 0
    completed: int = 0
    error: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None


_JOBS: dict[str, _JobState] = {}
_JOBS_LOCK = threading.Lock()


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
    started_domains: list[str]


class DomainRow(BaseModel):
    domain: str
    status: Literal["pending", "running", "completed"]
    latest_rates: EvalMetricsRates | None = None


class DomainsListResponse(BaseModel):
    tenant_id: str
    run_id: str | None
    domains: list[DomainRow]


class JobStatusResponse(BaseModel):
    job_id: str
    tenant_id: str
    status: Literal["running", "completed", "failed"]
    total: int
    completed: int
    error: str | None = None
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


def _running_domains_for_tenant(tenant_id: str) -> set[str]:
    with _JOBS_LOCK:
        running_jobs = [j for j in _JOBS.values() if j.tenant_id == tenant_id and j.status == "running"]
    out: set[str] = set()
    for job in running_jobs:
        out.update(job.domains)
    return out


def _start_job(tenant_id: str, domains: list[str]) -> _JobState:
    job_id = uuid4().hex
    total = len(domains) if domains else 1
    state = _JobState(
        job_id=job_id,
        tenant_id=tenant_id,
        domains=domains,
        total=total,
    )
    with _JOBS_LOCK:
        _JOBS[job_id] = state

    def _runner() -> None:
        try:
            if domains:
                for domain in domains:
                    result = run_eval_sync(tenant_id, domain)
                    with _JOBS_LOCK:
                        state.completed += 1
                        if result.get("ok") is False and state.error is None:
                            state.error = str(result.get("error") or "Evaluation failed")
            else:
                result = run_eval_sync(tenant_id, None)
                with _JOBS_LOCK:
                    state.completed = 1
                    if result.get("ok") is False:
                        state.error = str(result.get("error") or "Evaluation failed")
            with _JOBS_LOCK:
                state.status = "failed" if state.error else "completed"
                state.finished_at = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            with _JOBS_LOCK:
                state.status = "failed"
                state.error = str(exc)
                state.finished_at = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=_runner, daemon=True).start()
    return state


@router.get("/tenants/{tenant_id}/domains", response_model=DomainsListResponse)
async def list_domains(tenant_id: str, auth_tenant_id: TenantId) -> DomainsListResponse:
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    monitored = list_eval_domains(tenant)
    run = get_latest_eval_run(tenant)
    per_domain: dict[str, EvalMetricsRates] = {}
    run_id: str | None = None
    if run is not None:
        run_id = str(run.id)
        metrics = get_eval_metrics_for_run(tenant, run.id)
        per_domain = {
            str(domain): EvalMetricsRates.model_validate(rates)
            for domain, rates in (metrics.get("per_domain") or {}).items()
            if domain
        }
    running_domains = _running_domains_for_tenant(tenant)
    all_domains = sorted(set(monitored) | set(per_domain.keys()) | running_domains)
    rows: list[DomainRow] = []
    for domain in all_domains:
        rates = per_domain.get(domain)
        if domain in running_domains:
            status: Literal["pending", "running", "completed"] = "running"
        elif rates is not None:
            status = "completed"
        else:
            status = "pending"
        rows.append(DomainRow(domain=domain, status=status, latest_rates=rates))
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
    state = _start_job(tenant, normalized)
    return DomainsEvaluateResponse(
        status="started",
        message="Evaluation started",
        job_id=state.job_id,
        started_domains=normalized,
    )


@router.get("/tenants/{tenant_id}/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(tenant_id: str, job_id: str, auth_tenant_id: TenantId) -> JobStatusResponse:
    tenant = _enforce_tenant_match(tenant_id, auth_tenant_id)
    with _JOBS_LOCK:
        state = _JOBS.get(job_id)
    if state is None or state.tenant_id != tenant:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=state.job_id,
        tenant_id=state.tenant_id,
        status=state.status,
        total=state.total,
        completed=state.completed,
        error=state.error,
        started_at=state.started_at,
        finished_at=state.finished_at,
    )
