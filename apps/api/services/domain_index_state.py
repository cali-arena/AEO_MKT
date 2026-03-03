"""Domain index state service: compute desired version hashes, check if index is up to date, ensure ingested."""

import hashlib
import logging
from typing import Any

from apps.api.services.domain_ingest_jobs import (
    enqueue_domain_ingest_job,
    get_pending_or_running_ingest_job_id_for_domain,
)
from apps.api.services.policy import load_policy
from apps.api.services.policy import crawl_policy_version as get_crawl_policy_version
from apps.api.services.repo import (
    get_domain_index_state,
    get_entity_ids_for_sections,
    get_sections_by_domain,
    upsert_domain_index_state,
)

logger = logging.getLogger(__name__)


def compute_desired_index_version(tenant_id: str, domain: str) -> dict[str, str]:
    """
    Compute desired ac_version_hash, ec_version_hash, crawl_policy_version for (tenant_id, domain).
    Uses existing content versioning: section section_id+version_hash for AC/EC, policy hash for crawl.
    Returns dict with keys: ac_version_hash, ec_version_hash, crawl_policy_version (all non-empty when domain has content).
    """
    sections = get_sections_by_domain(tenant_id, domain)
    policy = load_policy()
    crawl_ver = get_crawl_policy_version(policy)

    if not sections:
        return {
            "ac_version_hash": "",
            "ec_version_hash": "",
            "crawl_policy_version": crawl_ver,
        }

    # AC desired: same pattern as EC (hash of section signatures). No separate AC hash util exists; reuse EC-style payload.
    section_sigs = "|".join(sorted(f"{s['section_id']}:{s.get('version_hash', '')}" for s in sections))
    ac_version_hash = hashlib.sha256(section_sigs.encode("utf-8")).hexdigest()[:16]

    # EC desired: section_sigs || entity_sigs (same formula as index_ec.build_ec)
    section_ids = [s["section_id"] for s in sections]
    entity_ids = get_entity_ids_for_sections(tenant_id, section_ids)
    entity_sigs = "|".join(sorted(entity_ids))
    payload = f"{section_sigs}||{entity_sigs}"
    ec_version_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    return {
        "ac_version_hash": ac_version_hash,
        "ec_version_hash": ec_version_hash,
        "crawl_policy_version": crawl_ver,
    }


def _state_hashes_match_desired(state: dict[str, Any] | None, desired: dict[str, Any]) -> bool:
    """Return True if state exists and its stored hashes match desired (any status)."""
    if state is None:
        return False
    return (
        (state.get("ac_version_hash") or "") == (desired.get("ac_version_hash") or "")
        and (state.get("ec_version_hash") or "") == (desired.get("ec_version_hash") or "")
        and (state.get("crawl_policy_version") or "") == (desired.get("crawl_policy_version") or "")
    )


def is_index_up_to_date(state: dict[str, Any] | None, desired: dict[str, Any]) -> bool:
    """
    Return True only if state is DONE and stored hashes match desired.
    If state is None or status != DONE, returns False.
    """
    if state is None:
        return False
    if (state.get("status") or "").upper() != "DONE":
        return False
    return _state_hashes_match_desired(state, desired)


def ensure_ingested(
    tenant_id: str,
    domain: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    Idempotent, version-aware ensure domain is ingested (indexed). If already DONE with matching
    hashes, return without enqueueing. If PENDING/RUNNING with same desired hashes, return
    existing job id. Otherwise enqueue one ingest job and upsert state to PENDING with desired
    hashes and clear last_error.
    Returns {status, desired, state, ingest_job_id, already_enqueued}.
    """
    desired = compute_desired_index_version(tenant_id, domain)
    state = get_domain_index_state(tenant_id, domain)

    if reason:
        logger.info(
            "ensure_ingested tenant_id=%s domain=%s reason=%s desired_ac=%s desired_ec=%s",
            tenant_id,
            domain,
            reason,
            desired.get("ac_version_hash", ""),
            desired.get("ec_version_hash", ""),
        )

    # Already DONE and hashes match => no job
    if is_index_up_to_date(state, desired):
        return {
            "status": "DONE",
            "desired": desired,
            "state": state,
            "ingest_job_id": None,
            "already_enqueued": False,
        }

    # PENDING or RUNNING with same desired hashes => return existing job (idempotent)
    state_status = (state.get("status") or "").upper() if state else ""
    if state_status in ("PENDING", "RUNNING") and _state_hashes_match_desired(state, desired):
        existing_job_id = get_pending_or_running_ingest_job_id_for_domain(tenant_id, domain)
        return {
            "status": state_status,
            "desired": desired,
            "state": state,
            "ingest_job_id": existing_job_id,
            "already_enqueued": True,
        }

    # FAILED (or None / other) or hashes changed => allow enqueue. Upsert PENDING with desired, clear last_error.
    upsert_domain_index_state(
        tenant_id,
        domain,
        status="PENDING",
        ac_version_hash=desired.get("ac_version_hash"),
        ec_version_hash=desired.get("ec_version_hash"),
        crawl_policy_version=desired.get("crawl_policy_version"),
        last_error=None,
    )
    job = enqueue_domain_ingest_job(
        tenant_id,
        domain,
        desired_hashes=desired,
        requested_by=reason,
    )
    job_id = job.get("id")
    updated_state = get_domain_index_state(tenant_id, domain)

    logger.info(
        "ensure_ingested_enqueued tenant_id=%s domain=%s ingest_job_id=%s desired_ac=%s desired_ec=%s",
        tenant_id,
        domain,
        job_id,
        desired.get("ac_version_hash", ""),
        desired.get("ec_version_hash", ""),
    )

    return {
        "status": "PENDING",
        "desired": desired,
        "state": updated_state,
        "ingest_job_id": job_id,
        "already_enqueued": False,
    }
