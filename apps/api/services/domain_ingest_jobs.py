"""DB-backed queue operations for domain ingest jobs (crawl/ingest/index per tenant+domain)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from apps.api.db import get_db
from apps.api.services.tenant_guard import require_tenant_id

INGEST_JOB_STATUSES = {"PENDING", "RUNNING", "DONE", "FAILED"}


def _row_to_job(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "domain": str(row["domain"]),
        "status": str(row["status"]).upper(),
        "desired_ac_version_hash": row.get("desired_ac_version_hash"),
        "desired_ec_version_hash": row.get("desired_ec_version_hash"),
        "desired_crawl_policy_version": row.get("desired_crawl_policy_version"),
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "updated_at": row.get("updated_at"),
        "error_code": row.get("error_code"),
        "error_message": row.get("error_message"),
        "requested_by": row.get("requested_by"),
    }


def enqueue_domain_ingest_job(
    tenant_id: str,
    domain: str,
    desired_hashes: dict[str, str | None],
    *,
    requested_by: str | None = None,
) -> dict[str, Any]:
    """
    Enqueue an ingest job for (tenant_id, domain) with desired version hashes. Idempotent:
    if a PENDING or RUNNING job already exists for the same tenant+domain+desired hashes,
    return that job; otherwise create and return a new one.
    """
    tenant_id = require_tenant_id(tenant_id)
    domain = (domain or "").strip().lower()
    if not domain:
        raise ValueError("domain is required")
    ac = desired_hashes.get("ac_version_hash")
    ec = desired_hashes.get("ec_version_hash")
    crawl = desired_hashes.get("crawl_policy_version")

    # Idempotent: find existing PENDING/RUNNING with same tenant+domain+desired hashes
    stmt_existing = text(
        """
        SELECT id, tenant_id, domain, status, desired_ac_version_hash, desired_ec_version_hash,
               desired_crawl_policy_version, created_at, started_at, finished_at, updated_at,
               error_code, error_message, requested_by
        FROM domain_ingest_job
        WHERE tenant_id = :tenant_id AND domain = :domain
          AND status IN ('PENDING', 'RUNNING')
          AND (desired_ac_version_hash IS NOT DISTINCT FROM :ac)
          AND (desired_ec_version_hash IS NOT DISTINCT FROM :ec)
          AND (desired_crawl_policy_version IS NOT DISTINCT FROM :crawl)
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    with get_db() as session:
        row = session.execute(
            stmt_existing,
            {"tenant_id": tenant_id, "domain": domain, "ac": ac, "ec": ec, "crawl": crawl},
        ).mappings().first()
        if row is not None:
            return _row_to_job(row)

        job_id = uuid.uuid4()
        stmt_insert = text(
            """
            INSERT INTO domain_ingest_job (
                id, tenant_id, domain, status,
                desired_ac_version_hash, desired_ec_version_hash, desired_crawl_policy_version,
                requested_by
            )
            VALUES (
                :job_id, :tenant_id, :domain, 'PENDING',
                :ac, :ec, :crawl, :requested_by
            )
            RETURNING id, tenant_id, domain, status, desired_ac_version_hash, desired_ec_version_hash,
                      desired_crawl_policy_version, created_at, started_at, finished_at, updated_at,
                      error_code, error_message, requested_by
            """
        )
        row = session.execute(
            stmt_insert,
            {
                "job_id": str(job_id),
                "tenant_id": tenant_id,
                "domain": domain,
                "ac": ac,
                "ec": ec,
                "crawl": crawl,
                "requested_by": requested_by,
            },
        ).mappings().first()
    if row is None:
        raise RuntimeError("failed to enqueue domain ingest job")
    return _row_to_job(row)


def get_domain_ingest_job(job_id: str) -> dict[str, Any] | None:
    """Return ingest job by id, or None. Not tenant-scoped (job_id is unique)."""
    stmt = text(
        """
        SELECT id, tenant_id, domain, status, desired_ac_version_hash, desired_ec_version_hash,
               desired_crawl_policy_version, created_at, started_at, finished_at, updated_at,
               error_code, error_message, requested_by
        FROM domain_ingest_job
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        row = session.execute(stmt, {"job_id": job_id}).mappings().first()
    if row is None:
        return None
    return _row_to_job(row)


def set_domain_ingest_job_running(job_id: str) -> None:
    """Mark ingest job as RUNNING and set started_at to now."""
    stmt = text(
        """
        UPDATE domain_ingest_job
        SET status = 'RUNNING', started_at = NOW(), updated_at = NOW()
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        session.execute(stmt, {"job_id": job_id})


def finish_domain_ingest_job(
    job_id: str,
    *,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Mark ingest job as DONE or FAILED; set finished_at and optional error fields."""
    s = (status or "").upper().strip()
    if s not in INGEST_JOB_STATUSES:
        raise ValueError(f"invalid status: {status}")
    stmt = text(
        """
        UPDATE domain_ingest_job
        SET status = :status, finished_at = NOW(), updated_at = NOW(),
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
                "error_code": error_code,
                "error_message": error_message,
            },
        )


def get_latest_ingest_job_statuses_for_tenant(tenant_id: str) -> dict[str, dict[str, Any]]:
    """Return latest ingest job per domain for tenant (for UI polling). Keyed by domain."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = text(
        """
        SELECT DISTINCT ON (domain)
               id, tenant_id, domain, status, desired_ac_version_hash, desired_ec_version_hash,
               desired_crawl_policy_version, created_at, started_at, finished_at, updated_at,
               error_code, error_message, requested_by
        FROM domain_ingest_job
        WHERE tenant_id = :tenant_id
        ORDER BY domain, created_at DESC
        """
    )
    with get_db() as session:
        rows = session.execute(stmt, {"tenant_id": tenant_id}).mappings().all()
    return {str(r["domain"]): _row_to_job(r) for r in rows}


def get_pending_or_running_ingest_job_id_for_domain(tenant_id: str, domain: str) -> str | None:
    """Return the latest PENDING or RUNNING ingest job id for (tenant_id, domain), or None. Tenant-scoped."""
    tenant_id = require_tenant_id(tenant_id)
    domain = (domain or "").strip().lower()
    if not domain:
        return None
    stmt = text(
        """
        SELECT id FROM domain_ingest_job
        WHERE tenant_id = :tenant_id AND domain = :domain
          AND status IN ('PENDING', 'RUNNING')
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    with get_db() as session:
        row = session.execute(stmt, {"tenant_id": tenant_id, "domain": domain}).first()
    if row is None:
        return None
    return str(row[0])


def claim_domain_ingest_job() -> dict[str, Any] | None:
    """Claim one PENDING ingest job (set RUNNING, started_at). Returns job dict or None."""
    stmt = text(
        """
        UPDATE domain_ingest_job AS j
        SET status = 'RUNNING', started_at = NOW(), updated_at = NOW()
        FROM (
            SELECT id FROM domain_ingest_job
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        ) AS picked
        WHERE j.id = picked.id
        RETURNING j.id, j.tenant_id, j.domain, j.status, j.desired_ac_version_hash, j.desired_ec_version_hash,
                  j.desired_crawl_policy_version, j.created_at, j.started_at, j.finished_at, j.updated_at,
                  j.error_code, j.error_message, j.requested_by
        """
    )
    with get_db() as session:
        row = session.execute(stmt).mappings().first()
    if row is None:
        return None
    return _row_to_job(row)


def clear_domain_ingest_jobs_for_tenant(tenant_id: str) -> int:
    """Delete all domain_ingest_job rows for the tenant. Returns number of rows deleted."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = text("DELETE FROM domain_ingest_job WHERE tenant_id = :tenant_id")
    with get_db() as session:
        result = session.execute(stmt, {"tenant_id": tenant_id})
        return result.rowcount or 0
