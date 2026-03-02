"""Tests for tenant-scoped domains routes."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def _auth(tenant: str) -> dict[str, str]:
    return {"Authorization": f"Bearer tenant:{tenant}"}


def test_list_domains_combines_monitored_and_latest_metrics() -> None:
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    fake_run_id = uuid.uuid4()
    with patch("apps.api.routes.domains.list_eval_domains", return_value=["alpha.com"]), patch(
        "apps.api.routes.domains.get_latest_eval_run",
        return_value=type("Run", (), {"id": fake_run_id})(),
    ), patch(
        "apps.api.routes.domains.get_eval_metrics_for_run",
        return_value={
            "per_domain": {
                "beta.com": {
                    "mention_rate": 1.0,
                    "citation_rate": 0.5,
                    "attribution_rate": 0.75,
                    "hallucination_rate": 0.0,
                }
            }
        },
    ), patch(
        "apps.api.routes.domains.get_latest_domain_job_statuses",
        return_value={},
    ):
        res = client.get(f"/tenants/{tenant}/domains", headers=_auth(tenant))
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_id"] == tenant
    assert body["run_id"] == str(fake_run_id)
    rows = {row["domain"]: row for row in body["domains"]}
    assert rows["alpha.com"]["status"] == "pending"
    assert rows["beta.com"]["status"] == "done"


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


def test_evaluate_domains_returns_job_and_job_status() -> None:
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    with patch("apps.api.routes.domains.add_eval_domain", return_value=True), patch(
        "apps.api.routes.domains.enqueue_domain_eval_job",
        return_value={
            "id": "9f3021a6-8e6c-454a-95e2-a9dbcc8358dd",
            "run_id": None,
            "tenant_id": tenant,
            "status": "PENDING",
            "total": 1,
            "completed": 0,
            "error_message": None,
            "started_at": None,
            "finished_at": None,
        },
    ), patch(
        "apps.api.routes.domains.get_domain_eval_job",
        return_value={
            "id": "9f3021a6-8e6c-454a-95e2-a9dbcc8358dd",
            "tenant_id": tenant,
            "status": "RUNNING",
            "total": 1,
            "completed": 1,
            "error_message": None,
            "started_at": None,
            "finished_at": None,
        },
    ):
        start = client.post(
            f"/tenants/{tenant}/domains/evaluate",
            headers=_auth(tenant),
            json={"domains": ["one.com"]},
        )
        assert start.status_code == 202
        body = start.json()
        assert "job_id" in body
        assert "status_url" in body
        assert body["status_url"] == f"/tenants/{tenant}/jobs/{body['job_id']}"
        job_id = body["job_id"]

        status = client.get(f"/tenants/{tenant}/jobs/{job_id}", headers=_auth(tenant))
        assert status.status_code == 200
        assert status.json()["status"] in {"running", "pending", "done", "failed"}
