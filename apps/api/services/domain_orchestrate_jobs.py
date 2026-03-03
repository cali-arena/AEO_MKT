"""DB-backed queue for domain orchestrate jobs (Way 1: sequential ensure->ingest->eval in worker).

Worker behavior: for each domain, ensure_ingested then run ingest inline if needed then run eval.
If ingest fails for a domain: orchestrate job is marked FAILED with error_code DOMAIN_NOT_INDEXED
and no further domains are processed.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from apps.api.db import get_db
from apps.api.services.tenant_guard import require_tenant_id

ORCHESTRATE_STATUSES = {"PENDING", "RUNNING", "DONE", "FAILED"}


def _row_to_job(row: Any) -> dict[str, Any]:
    domains = row.get("domains")
    if isinstance(domains, str):
        try:
            domains = json.loads(domains)
        except Exception:
            domains = []
    desired = row.get("desired_by_domain") or {}
    if isinstance(desired, str):
        try:
            desired = json.loads(desired)
        except Exception:
            desired = {}
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "domains": list(domains or []),
        "desired_by_domain": dict(desired),
        "status": str(row["status"]).upper(),
        "completed_domains": int(row.get("completed_domains") or 0),
        "current_domain": row.get("current_domain"),
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "error_code": row.get("error_code"),
        "error_message": row.get("error_message"),
    }


def enqueue_domain_orchestrate_job(
    tenant_id: str,
    domains: list[str],
    desired_by_domain: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Enqueue one orchestrate job. Payload: tenant_id, domains, desired_by_domain (domain -> {ac_version_hash, ec_version_hash, crawl_policy_version})."""
    tenant_id = require_tenant_id(tenant_id)
    job_id = uuid.uuid4()
    domains_json = json.dumps(domains)
    desired_json = json.dumps(desired_by_domain)
    stmt = text(
        """
        INSERT INTO domain_orchestrate_job (id, tenant_id, domains, desired_by_domain, status)
        VALUES (:job_id, :tenant_id, CAST(:domains_json AS jsonb), CAST(:desired_json AS jsonb), 'PENDING')
        RETURNING id, tenant_id, domains, desired_by_domain, status, completed_domains,
                  created_at, started_at, finished_at, error_code, error_message
        """
    )
    with get_db() as session:
        row = session.execute(
            stmt,
            {
                "job_id": str(job_id),
                "tenant_id": tenant_id,
                "domains_json": domains_json,
                "desired_json": desired_json,
            },
        ).mappings().first()
    if row is None:
        raise RuntimeError("failed to enqueue domain orchestrate job")
    return _row_to_job(row)


def get_domain_orchestrate_job(job_id: str) -> dict[str, Any] | None:
    """Return orchestrate job by id (includes current_domain when present)."""
    stmt = text(
        """
        SELECT id, tenant_id, domains, desired_by_domain, status, completed_domains,
               current_domain, created_at, started_at, finished_at, error_code, error_message
        FROM domain_orchestrate_job
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        row = session.execute(stmt, {"job_id": job_id}).mappings().first()
    if row is None:
        return None
    return _row_to_job(row)


def claim_domain_orchestrate_job() -> dict[str, Any] | None:
    """Claim one PENDING orchestrate job (set RUNNING, started_at). Returns job dict or None."""
    stmt = text(
        """
        UPDATE domain_orchestrate_job AS j
        SET status = 'RUNNING', started_at = NOW()
        FROM (
            SELECT id FROM domain_orchestrate_job
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        ) AS picked
        WHERE j.id = picked.id
        RETURNING j.id, j.tenant_id, j.domains, j.desired_by_domain, j.status, j.completed_domains,
                  j.current_domain, j.created_at, j.started_at, j.finished_at, j.error_code, j.error_message
        """
    )
    with get_db() as session:
        row = session.execute(stmt).mappings().first()
    if row is None:
        return None
    return _row_to_job(row)


def set_orchestrate_current_domain(job_id: str, current_domain: str | None) -> None:
    """Set current_domain (domain being evaluated); None to clear. For EVALUATING status derivation."""
    stmt = text(
        """
        UPDATE domain_orchestrate_job
        SET current_domain = :current_domain
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        session.execute(stmt, {"job_id": job_id, "current_domain": current_domain})


def get_running_orchestrate_current_domain(tenant_id: str) -> str | None:
    """Return current_domain of the tenant's RUNNING orchestrate job, if any. For derived status EVALUATING."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = text(
        """
        SELECT current_domain FROM domain_orchestrate_job
        WHERE tenant_id = :tenant_id AND status = 'RUNNING' AND current_domain IS NOT NULL
        ORDER BY started_at DESC NULLS LAST
        LIMIT 1
        """
    )
    with get_db() as session:
        row = session.execute(stmt, {"tenant_id": tenant_id}).first()
    if row is None or not row[0]:
        return None
    return str(row[0]).strip().lower()


def finish_domain_orchestrate_job(
    job_id: str,
    status: str,
    *,
    completed_domains: int | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Mark orchestrate job DONE or FAILED; set finished_at and optional error/progress."""
    s = (status or "").upper().strip()
    if s not in ORCHESTRATE_STATUSES:
        raise ValueError(f"invalid status: {status}")
    stmt = text(
        """
        UPDATE domain_orchestrate_job
        SET status = :status, finished_at = NOW(),
            completed_domains = COALESCE(:completed_domains, completed_domains),
            error_code = :error_code, error_message = :error_message
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        session.execute(
            stmt,
            {
                "job_id": job_id,
                "status": s,
                "completed_domains": completed_domains,
                "error_code": error_code,
                "error_message": error_message,
            },
        )


def update_orchestrate_progress(job_id: str, completed_domains: int) -> None:
    """Update completed_domains count (optional progress)."""
    stmt = text(
        """
        UPDATE domain_orchestrate_job
        SET completed_domains = :completed_domains
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        session.execute(stmt, {"job_id": job_id, "completed_domains": completed_domains})
