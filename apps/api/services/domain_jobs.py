"""DB-backed queue operations for domain evaluation jobs."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import text

from apps.api.db import get_db
from apps.api.services.tenant_guard import require_tenant_id

ALLOWED_JOB_STATUSES = {"PENDING", "RUNNING", "DONE", "FAILED"}


def _normalize_domains(domains: Sequence[str] | None) -> list[str]:
    if not domains:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for value in domains:
        d = str(value or "").strip().lower()
        if not d or d in seen:
            continue
        seen.add(d)
        out.append(d)
    return out


def _row_to_job(row: Any) -> dict[str, Any]:
    domains = row.get("domains") if hasattr(row, "get") else None
    if isinstance(domains, str):
        try:
            domains = json.loads(domains)
        except Exception:
            domains = []
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "domains": list(domains or []),
        "status": str(row["status"]).upper(),
        "total": int(row["total"] or 0),
        "completed": int(row["completed"] or 0),
        "error_message": row.get("error_message"),
        "error_code": row.get("error_code"),
        "run_id": str(row["run_id"]) if row.get("run_id") else None,
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "worker_id": row.get("worker_id"),
    }


def enqueue_domain_eval_job(tenant_id: str | None, domains: Sequence[str] | None) -> dict[str, Any]:
    tenant_id = require_tenant_id(tenant_id)
    normalized = _normalize_domains(domains)
    total = len(normalized) if normalized else 1
    job_id = uuid.uuid4()
    stmt = text(
        """
        INSERT INTO domain_eval_job (id, tenant_id, domains, status, total, completed)
        VALUES (:job_id, :tenant_id, CAST(:domains_json AS jsonb), 'PENDING', :total, 0)
        RETURNING id, tenant_id, domains, status, total, completed, error_message, error_code, run_id,
                  created_at, started_at, finished_at, worker_id
        """
    )
    with get_db() as session:
        row = session.execute(
            stmt,
            {
                "job_id": str(job_id),
                "tenant_id": tenant_id,
                "domains_json": json.dumps(normalized),
                "total": total,
            },
        ).mappings().first()
    if row is None:
        raise RuntimeError("failed to enqueue domain evaluation job")
    return _row_to_job(row)


def enqueue_domain_eval_job_if_absent(
    tenant_id: str | None,
    domains: Sequence[str] | None,
) -> tuple[dict[str, Any], bool]:
    """
    Enqueue a domain eval job unless an overlapping PENDING/RUNNING job already exists.
    Returns (job, created):
    - created=True: inserted a new PENDING job
    - created=False: returned existing overlapping active job
    """
    tenant_id = require_tenant_id(tenant_id)
    normalized = _normalize_domains(domains)
    total = len(normalized) if normalized else 1
    job_id = uuid.uuid4()
    lock_key = f"domain_eval_enqueue:{tenant_id}"

    select_overlap_stmt = text(
        """
        SELECT id, tenant_id, domains, status, total, completed, error_message, error_code, run_id,
               created_at, started_at, finished_at, worker_id
        FROM domain_eval_job
        WHERE tenant_id = :tenant_id
          AND status IN ('PENDING', 'RUNNING')
          AND (
            jsonb_array_length(CAST(:domains_json AS jsonb)) = 0
            OR domains ?| CAST(:domains AS text[])
          )
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    insert_stmt = text(
        """
        INSERT INTO domain_eval_job (id, tenant_id, domains, status, total, completed)
        VALUES (:job_id, :tenant_id, CAST(:domains_json AS jsonb), 'PENDING', :total, 0)
        RETURNING id, tenant_id, domains, status, total, completed, error_message, error_code, run_id,
                  created_at, started_at, finished_at, worker_id
        """
    )
    with get_db() as session:
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key)::bigint)"),
            {"lock_key": lock_key},
        )
        overlap = session.execute(
            select_overlap_stmt,
            {
                "tenant_id": tenant_id,
                "domains_json": json.dumps(normalized),
                "domains": normalized,
            },
        ).mappings().first()
        if overlap is not None:
            return _row_to_job(overlap), False
        inserted = session.execute(
            insert_stmt,
            {
                "job_id": str(job_id),
                "tenant_id": tenant_id,
                "domains_json": json.dumps(normalized),
                "total": total,
            },
        ).mappings().first()
    if inserted is None:
        raise RuntimeError("failed to enqueue domain evaluation job")
    return _row_to_job(inserted), True


def claim_domain_eval_job(worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
    stmt = text(
        """
        WITH picked AS (
            SELECT id
            FROM domain_eval_job
            WHERE status = 'PENDING'
               OR (status = 'RUNNING' AND lease_expires_at IS NOT NULL AND lease_expires_at < NOW())
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE domain_eval_job AS j
        SET status = 'RUNNING',
            started_at = COALESCE(j.started_at, NOW()),
            finished_at = NULL,
            error_message = NULL,
            error_code = NULL,
            worker_id = :worker_id,
            lease_expires_at = NOW() + (CAST(:lease_seconds AS TEXT) || ' seconds')::interval
        FROM picked
        WHERE j.id = picked.id
        RETURNING j.id, j.tenant_id, j.domains, j.status, j.total, j.completed, j.error_message, j.error_code, j.run_id,
                  j.created_at, j.started_at, j.finished_at, j.worker_id
        """
    )
    with get_db() as session:
        row = session.execute(
            stmt,
            {"worker_id": worker_id, "lease_seconds": int(lease_seconds)},
        ).mappings().first()
    if row is None:
        return None
    return _row_to_job(row)


def finish_domain_eval_job(
    job_id: str,
    *,
    status: str,
    completed: int,
    error_message: str | None = None,
    error_code: str | None = None,
    run_id: str | None = None,
) -> None:
    normalized_status = status.upper().strip()
    if normalized_status not in ALLOWED_JOB_STATUSES:
        raise ValueError(f"invalid status: {status}")
    stmt = text(
        """
        UPDATE domain_eval_job
        SET status = :status,
            completed = :completed,
            error_message = :error_message,
            error_code = :error_code,
            run_id = CAST(:run_id AS uuid),
            finished_at = NOW(),
            lease_expires_at = NULL
        WHERE id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        session.execute(
            stmt,
            {
                "job_id": job_id,
                "status": normalized_status,
                "completed": max(int(completed), 0),
                "error_message": error_message,
                "error_code": error_code,
                "run_id": run_id,
            },
        )


def get_domain_eval_job(tenant_id: str | None, job_id: str) -> dict[str, Any] | None:
    tenant_id = require_tenant_id(tenant_id)
    stmt = text(
        """
        SELECT id, tenant_id, domains, status, total, completed, error_message, error_code, run_id,
               created_at, started_at, finished_at, worker_id
        FROM domain_eval_job
        WHERE tenant_id = :tenant_id AND id = CAST(:job_id AS uuid)
        """
    )
    with get_db() as session:
        row = session.execute(stmt, {"tenant_id": tenant_id, "job_id": job_id}).mappings().first()
    if row is None:
        return None
    return _row_to_job(row)


def get_latest_domain_job_statuses(tenant_id: str | None) -> dict[str, str]:
    tenant_id = require_tenant_id(tenant_id)
    stmt = text(
        """
        SELECT DISTINCT ON (x.domain)
               x.domain,
               x.status
        FROM (
            SELECT jsonb_array_elements_text(j.domains) AS domain,
                   j.status AS status,
                   COALESCE(j.finished_at, j.started_at, j.created_at) AS ts
            FROM domain_eval_job AS j
            WHERE j.tenant_id = :tenant_id
              AND jsonb_array_length(j.domains) > 0
        ) AS x
        ORDER BY x.domain, x.ts DESC
        """
    )
    with get_db() as session:
        rows = session.execute(stmt, {"tenant_id": tenant_id}).all()
    return {str(r[0]): str(r[1]).upper() for r in rows}


def get_pending_or_running_job_id_for_domain(tenant_id: str | None, domain: str) -> str | None:
    """Return job id of the latest PENDING or RUNNING job that includes this domain, or None. Tenant-scoped."""
    tenant_id = require_tenant_id(tenant_id)
    domain_json = json.dumps([domain.strip().lower()])
    stmt = text(
        """
        SELECT id
        FROM domain_eval_job
        WHERE tenant_id = :tenant_id
          AND status IN ('PENDING', 'RUNNING')
          AND domains @> CAST(:domain_json AS jsonb)
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    with get_db() as session:
        row = session.execute(
            stmt,
            {"tenant_id": tenant_id, "domain_json": domain_json},
        ).first()
    if row is None:
        return None
    return str(row[0])


def clear_domain_eval_jobs_for_tenant(tenant_id: str | None) -> int:
    """Delete all domain_eval_job rows for the tenant. Returns number of rows deleted."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = text("DELETE FROM domain_eval_job WHERE tenant_id = :tenant_id")
    with get_db() as session:
        result = session.execute(stmt, {"tenant_id": tenant_id})
        return result.rowcount or 0
