"""Tests for tenant-scoped domains routes."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def _auth(tenant: str) -> dict[str, str]:
    return {"Authorization": f"Bearer tenant:{tenant}"}


def test_list_domains_combines_status_and_aggregates_ui_status_drives_done() -> None:
    """list_domains uses get_domains_with_status (index + eval join); ui_status drives display so DONE only when indexed + eval done."""
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    fake_run_id = uuid.uuid4()
    with patch(
        "apps.api.routes.domains.get_domains_with_status",
        return_value=[
            {
                "domain": "alpha.com",
                "index_status": "UNINDEXED",
                "last_indexed_at": None,
                "index_error": None,
                "eval_status": "NONE",
                "orchestration_status": None,
                "ui_status": "UNINDEXED",
            },
            {
                "domain": "beta.com",
                "index_status": "DONE",
                "last_indexed_at": None,
                "index_error": None,
                "eval_status": "DONE",
                "orchestration_status": None,
                "ui_status": "DONE",
            },
        ],
    ), patch(
        "apps.api.routes.domains.get_latest_eval_run",
        return_value=type("Run", (), {"id": fake_run_id})(),
    ), patch(
        "apps.api.routes.domains.get_domain_aggregates_from_eval_result",
        return_value=[
            {
                "domain": "beta.com",
                "total_results": 10,
                "refused_count": 0,
                "ok_count": 10,
                "mention_rate": 1.0,
                "citation_rate": 0.5,
                "attribution_rate": 0.75,
                "hallucination_rate": 0.0,
                "refusal_reason_summary": None,
                "last_run_id": str(fake_run_id),
                "last_created_at": None,
            }
        ],
    ):
        res = client.get(f"/tenants/{tenant}/domains", headers=_auth(tenant))
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_id"] == tenant
    assert body["run_id"] == str(fake_run_id)
    rows = {row["domain"]: row for row in body["domains"]}
    assert rows["alpha.com"]["status"] == "pending"
    assert rows["alpha.com"]["ui_status"] == "UNINDEXED"
    assert rows["beta.com"]["status"] == "done"
    assert rows["beta.com"]["ui_status"] == "DONE"


def test_create_domains_normalizes_and_returns_created_existing() -> None:
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"

    def _add(_tenant: str, domain: str) -> bool:
        return domain != "exists.com"

    with patch("apps.api.routes.domains.add_eval_domain", side_effect=_add):
        res = client.post(
            f"/tenants/{tenant}/domains",
            headers=_auth(tenant),
            json={"domains": ["https://New.com/path", "exists.com", "NEW.com"]},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["created"] == ["new.com"]
    assert body["existing"] == ["exists.com"]


def test_evaluate_domains_all_done_returns_orchestration_job_and_domains_state() -> None:
    """All domains DONE => enqueue orchestration job only; return orchestration_job_id and per-domain state."""
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    orch_id = "9f3021a6-8e6c-454a-95e2-a9dbcc8358dd"
    with patch("apps.api.routes.domains.add_eval_domain", return_value=True), patch(
        "apps.api.routes.domains.ensure_ingested",
        return_value={
            "status": "DONE",
            "desired": {"ac_version_hash": "", "ec_version_hash": "", "crawl_policy_version": "abc12"},
            "state": {},
            "ingest_job_id": None,
            "already_enqueued": False,
        },
    ), patch(
        "apps.api.routes.domains.enqueue_domain_eval_orchestration_job",
        return_value={"id": orch_id, "tenant_id": tenant, "domains": ["one.com"], "status": "PENDING"},
    ), patch("apps.api.routes.domains.get_domain_eval_job", return_value=None), patch(
        "apps.api.routes.domains.get_domain_ingest_job", return_value=None
    ), patch(
        "apps.api.routes.domains.get_domain_eval_orchestration_job",
        return_value={
            "id": orch_id,
            "tenant_id": tenant,
            "domains": ["one.com"],
            "status": "PENDING",
            "created_at": None,
            "updated_at": None,
        },
    ):
        start = client.post(
            f"/tenants/{tenant}/domains/evaluate",
            headers=_auth(tenant),
            json={"domains": ["one.com"]},
        )
        assert start.status_code == 202
        body = start.json()
        assert body["orchestration_job_id"] == orch_id
        assert body["job_id"] == orch_id
        assert body["index_status"] == "up_to_date"
        assert body["eval_job_id"] is None
        assert body["status_url"] == f"/tenants/{tenant}/jobs/{orch_id}"
        assert "desired_hashes" in body
        domains_state = body.get("domains_state") or []
        assert len(domains_state) == 1
        assert domains_state[0]["domain"] == "one.com" and domains_state[0]["state"] == "DONE"

        status = client.get(f"/tenants/{tenant}/jobs/{orch_id}", headers=_auth(tenant))
        assert status.status_code == 200
        assert status.json()["status"] in {"running", "pending", "done", "failed"}


def test_evaluate_domains_indexing_queued_returns_orchestration_and_domains_state() -> None:
    """When any domain not DONE, return orchestration_job_id, INDEXING in domains_state, ingest_job_id; no eval enqueue in route."""
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    ingest_job_id = "ingest-111-222"
    orch_id = "orch-456"
    with patch("apps.api.routes.domains.add_eval_domain", return_value=True), patch(
        "apps.api.routes.domains.ensure_ingested",
        return_value={
            "status": "PENDING",
            "desired": {"ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"},
            "state": {},
            "ingest_job_id": ingest_job_id,
            "already_enqueued": False,
        },
    ), patch(
        "apps.api.routes.domains.enqueue_domain_eval_orchestration_job",
        return_value={"id": orch_id, "tenant_id": tenant, "domains": ["one.com"], "status": "PENDING"},
    ):
        res = client.post(
            f"/tenants/{tenant}/domains/evaluate",
            headers=_auth(tenant),
            json={"domains": ["one.com"]},
        )
        assert res.status_code == 202
        body = res.json()
        assert body["eval_job_id"] is None
        assert body["orchestration_job_id"] == orch_id
        assert body["job_id"] == orch_id
        assert body["index_job_id"] == ingest_job_id
        assert body["index_status"] in ("pending", "running")
        domains_state = body.get("domains_state") or []
        assert len(domains_state) == 1
        assert domains_state[0]["state"] == "INDEXING" and domains_state[0]["ingest_job_id"] == ingest_job_id


def test_evaluate_enqueues_orchestration_per_request_same_ingest_in_domains_state() -> None:
    """Two evaluate calls each enqueue an orchestration job; ensure_ingested idempotency gives same ingest_job_id in domains_state."""
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    same_ingest_id = "ingest-same-123"
    orch_ids = ["orch-1", "orch-2"]
    orch_call = [0]

    def _ensure(tenant_id: str, domain: str, *, reason=None):
        return {
            "status": "PENDING",
            "desired": {"ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"},
            "state": {},
            "ingest_job_id": same_ingest_id,
            "already_enqueued": False,
        }

    def _enqueue_orch(tenant_id: str, domains: list, desired_hashes_per_domain: dict):
        idx = orch_call[0]
        orch_call[0] += 1
        return {"id": orch_ids[idx], "tenant_id": tenant_id, "domains": domains, "status": "PENDING"}

    with patch("apps.api.routes.domains.add_eval_domain", return_value=True), patch(
        "apps.api.routes.domains.ensure_ingested",
        side_effect=_ensure,
    ), patch("apps.api.routes.domains.enqueue_domain_eval_orchestration_job", side_effect=_enqueue_orch):
        r1 = client.post(
            f"/tenants/{tenant}/domains/evaluate",
            headers=_auth(tenant),
            json={"domains": ["one.com"]},
        )
        r2 = client.post(
            f"/tenants/{tenant}/domains/evaluate",
            headers=_auth(tenant),
            json={"domains": ["one.com"]},
        )
        assert r1.status_code == 202 and r2.status_code == 202
        assert r1.json()["job_id"] == "orch-1" and r2.json()["job_id"] == "orch-2"
        assert r1.json()["eval_job_id"] is None and r2.json()["eval_job_id"] is None
        assert r1.json()["index_job_id"] == same_ingest_id and r2.json()["index_job_id"] == same_ingest_id
        assert r1.json()["domains_state"][0]["ingest_job_id"] == same_ingest_id
        assert r2.json()["domains_state"][0]["ingest_job_id"] == same_ingest_id


def test_bulk_evaluate_enqueues_one_orchestration_ensure_ingested_per_domain() -> None:
    """Bulk evaluate_domains() enqueues exactly 1 orchestration job; ensure_ingested() called for each domain."""
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    domains = ["a.com", "b.com"]
    ensure_calls: list[tuple[str, str]] = []
    orch_calls: list[dict] = []

    def _ensure(tenant_id: str, domain: str, *, reason=None):
        ensure_calls.append((tenant_id, domain))
        return {
            "status": "PENDING",
            "desired": {"ac_version_hash": "x", "ec_version_hash": "y", "crawl_policy_version": "z"},
            "state": {},
            "ingest_job_id": f"ingest-{domain}",
            "already_enqueued": False,
        }

    def _enqueue_orch(tenant_id: str, domains_list: list, desired_hashes_per_domain: dict):
        orch_calls.append({"tenant_id": tenant_id, "domains": list(domains_list), "desired": desired_hashes_per_domain})
        return {"id": "orch-1", "tenant_id": tenant_id, "domains": domains_list, "status": "PENDING"}

    with patch("apps.api.routes.domains.add_eval_domain", return_value=True), patch(
        "apps.api.routes.domains.ensure_ingested",
        side_effect=_ensure,
    ), patch(
        "apps.api.routes.domains.enqueue_domain_eval_orchestration_job",
        side_effect=_enqueue_orch,
    ):
        res = client.post(
            f"/tenants/{tenant}/domains/evaluate",
            headers=_auth(tenant),
            json={"domains": domains},
        )
    assert res.status_code == 202
    assert len(ensure_calls) == 2
    assert ensure_calls == [(tenant, "a.com"), (tenant, "b.com")]
    assert len(orch_calls) == 1
    assert orch_calls[0]["domains"] == ["a.com", "b.com"]
    assert set(orch_calls[0]["desired"]) == {"a.com", "b.com"}
