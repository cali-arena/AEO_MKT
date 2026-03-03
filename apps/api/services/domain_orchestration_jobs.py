"""DB-backed queue for domain eval orchestration jobs (ensure ingested, then enqueue eval when all DONE)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from apps.api.db import get_db
from apps.api.services.tenant_guard import require_tenant_id


def _row_to_job(row: Any) -> dict[str, Any]:
    domains = row.get("domains")
    if isinstance(domains, str):
        try:
            domains = json.loads(domains)
        except Exception:
            domains = []
    hashes = row.get("desired_hashes_per_domain") or {}
    if isinstance(hashes, str):
        try:
            hashes = json.loads(hashes)
        except Exception:
            hashes = {}
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "domains": list(domains or []),
        "requested_at": row.get("requested_at"),
        "desired_hashes_per_domain": dict(hashes),
        "status": str(row["status"]).upper(),
        "eval_job_id": str(row["eval_job_id"]) if row.get("eval_job_id") else None,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def enqueue_domain_eval_orchestration_job(
    tenant_id: str,
    domains: list[str],
    desired_hashes_per_domain: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Enqueue one orchestration job. Payload: tenant_id, domains, requested_at, desired_hashes_per_domain."""
    tenant_id = require_tenant_id(tenant_id)
    job_id = uuid.uuid4()
    requested_at = datetime.now(timezone.utc)
    domains_json = json.dumps(domains)
    hashes_json = json.dumps(desired_hashes_per_domain)
    stmt = text(
        """
        INSERT INTO domain_eval_orchestration_job (
            id, tenant_id, domains, requested_at, desired_hashes_per_domain, status
        )
        VALUES (
            :job_id, :tenant_id, CAST(:domains_json AS jsonb), :requested_at,
            CAST(:hashes_json AS jsonb), 'PENDING'
        )
        RETURNING id, tenant_id, domains, requested_at, desired_hashes_per_domain, status,
                  eval_job_id, created_at, updated_at
        """
    )
    with get_db() as session:
        row = session.execute(
            stmt,
            {
                "job_id": str(job_id),
                "tenant_id": tenant_id,
                "domains_json": domains_json,
                "requested_at": requested_at,
                "hashes_json": hashes_json,
            },
        ).mappings().first()
    if row is None:
        raise RuntimeError("failed to enqueue domain eval orchestration job")
    return _row_to_job(row)


def get_domain_eval_orchestration_job(job_id: str) -> dict[str, Any] | None:
    """Return orchestration job by id. Not tenant-scoped (id is unique)."""
    stmt = text(
        """
        SELECT id, tenant_id, domains, requested_at, desired_hashes_per_domain, status,
               eval_job_id, created_at, updated_at
        FROM domain_eval_orchestration_job
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        row = session.execute(stmt, {"job_id": job_id}).mappings().first()
    if row is None:
        return None
    return _row_to_job(row)


def claim_domain_eval_orchestration_job() -> dict[str, Any] | None:
    """Claim one PENDING orchestration job (set RUNNING). Returns job dict or None."""
    stmt = text(
        """
        UPDATE domain_eval_orchestration_job AS j
        SET status = 'RUNNING', updated_at = NOW()
        FROM (
            SELECT id FROM domain_eval_orchestration_job
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        ) AS picked
        WHERE j.id = picked.id
        RETURNING j.id, j.tenant_id, j.domains, j.requested_at, j.desired_hashes_per_domain,
                  j.status, j.eval_job_id, j.created_at, j.updated_at
        """
    )
    with get_db() as session:
        row = session.execute(stmt).mappings().first()
    if row is None:
        return None
    return _row_to_job(row)


def finish_domain_eval_orchestration_job(
    job_id: str,
    status: str,
    eval_job_id: str | None = None,
) -> None:
    """Mark orchestration job DONE (with optional eval_job_id) or FAILED."""
    stmt = text(
        """
        UPDATE domain_eval_orchestration_job
        SET status = :status, eval_job_id = CAST(:eval_job_id AS uuid), updated_at = NOW()
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        session.execute(
            stmt,
            {"job_id": job_id, "status": status.upper(), "eval_job_id": eval_job_id},
        )


def set_orchestration_back_to_pending(job_id: str) -> None:
    """Set orchestration job back to PENDING (e.g. when domains not all indexed yet)."""
    stmt = text(
        """
        UPDATE domain_eval_orchestration_job
        SET status = 'PENDING', updated_at = NOW()
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        session.execute(stmt, {"job_id": job_id})
