"""Tests for domain index state service: ensure_ingested idempotency and version-aware enqueue."""

from __future__ import annotations

from unittest.mock import patch

from apps.api.services.domain_index_state import ensure_ingested

TENANT = "tenant-test-idempotency"
DOMAIN = "example.com"
DESIRED = {"ac_version_hash": "ac1", "ec_version_hash": "ec1", "crawl_policy_version": "crawl1"}
STATE_PENDING_SAME = {"status": "PENDING", "ac_version_hash": "ac1", "ec_version_hash": "ec1", "crawl_policy_version": "crawl1"}
INGEST_JOB_ID = "ingest-job-111"


def test_ensure_ingested_idempotent_two_calls_enqueue_once() -> None:
    """Calling ensure_ingested twice when index is missing/stale enqueues at most one ingest job."""
    get_state_calls: list[tuple[str, str]] = []
    enqueue_calls: list[tuple] = []

    def _get_state(tenant_id: str, domain: str):
        get_state_calls.append((tenant_id, domain))
        # First call: no state. Second call: PENDING with same hashes (simulate first call's upsert).
        if len(get_state_calls) == 1:
            return None
        return dict(STATE_PENDING_SAME)

    def _enqueue(tenant_id: str, domain: str, *, desired_hashes, requested_by=None):
        enqueue_calls.append((tenant_id, domain, desired_hashes, requested_by))
        return {"id": INGEST_JOB_ID, "tenant_id": tenant_id, "domain": domain, "status": "PENDING"}

    def _get_pending(tenant_id: str, domain: str):
        return INGEST_JOB_ID if len(get_state_calls) >= 2 else None

    with (
        patch("apps.api.services.domain_index_state.compute_desired_index_version", return_value=DESIRED),
        patch("apps.api.services.domain_index_state.get_domain_index_state", side_effect=_get_state),
        patch("apps.api.services.domain_index_state.upsert_domain_index_state"),
        patch("apps.api.services.domain_index_state.enqueue_domain_ingest_job", side_effect=_enqueue),
        patch("apps.api.services.domain_index_state.get_pending_or_running_ingest_job_id_for_domain", side_effect=_get_pending),
    ):
        r1 = ensure_ingested(TENANT, DOMAIN, reason="evaluate")
        r2 = ensure_ingested(TENANT, DOMAIN, reason="evaluate")

    assert len(enqueue_calls) == 1, "enqueue_domain_ingest_job should be called exactly once"
    assert r1["status"] == "PENDING" and r1["ingest_job_id"] == INGEST_JOB_ID
    assert r2["status"] == "PENDING" and r2["ingest_job_id"] == INGEST_JOB_ID and r2.get("already_enqueued") is True


def test_ensure_ingested_version_bump_enqueues_new_job() -> None:
    """When crawl_policy_version or embedding hashes change, ensure_ingested enqueues a new ingest job even if previously DONE."""
    old_hashes = {"ac_version_hash": "ac0", "ec_version_hash": "ec0", "crawl_policy_version": "crawl0"}
    new_hashes = {"ac_version_hash": "ac1", "ec_version_hash": "ec1", "crawl_policy_version": "crawl1"}
    state_done_old = {"status": "DONE", **old_hashes}
    enqueue_calls: list[dict] = []

    def _desired(tenant_id: str, domain: str):
        return new_hashes

    def _get_state(tenant_id: str, domain: str):
        return state_done_old

    def _enqueue(tenant_id: str, domain: str, *, desired_hashes, requested_by=None):
        enqueue_calls.append({"tenant_id": tenant_id, "domain": domain, "desired_hashes": desired_hashes})
        return {"id": "new-job-1", "tenant_id": tenant_id, "domain": domain, "status": "PENDING"}

    with (
        patch("apps.api.services.domain_index_state.compute_desired_index_version", side_effect=_desired),
        patch("apps.api.services.domain_index_state.get_domain_index_state", side_effect=_get_state),
        patch("apps.api.services.domain_index_state.upsert_domain_index_state"),
        patch("apps.api.services.domain_index_state.enqueue_domain_ingest_job", side_effect=_enqueue),
        patch("apps.api.services.domain_index_state.get_pending_or_running_ingest_job_id_for_domain", return_value=None),
    ):
        r = ensure_ingested(TENANT, DOMAIN, reason="evaluate")

    assert len(enqueue_calls) == 1
    assert enqueue_calls[0]["desired_hashes"] == new_hashes
    assert r["status"] == "PENDING" and r["ingest_job_id"] == "new-job-1"


def test_ensure_ingested_done_matching_skips_enqueue() -> None:
    """When index_state is DONE with matching hashes, ensure_ingested does not enqueue."""
    state_done = {"status": "DONE", **DESIRED}
    with (
        patch("apps.api.services.domain_index_state.compute_desired_index_version", return_value=DESIRED),
        patch("apps.api.services.domain_index_state.get_domain_index_state", return_value=state_done),
        patch("apps.api.services.domain_index_state.enqueue_domain_ingest_job") as enqueue,
    ):
        r = ensure_ingested(TENANT, DOMAIN, reason="evaluate")
    enqueue.assert_not_called()
    assert r["status"] == "DONE" and r["ingest_job_id"] is None
