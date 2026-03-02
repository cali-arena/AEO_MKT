"""Tests for tenant-scoped domains routes."""

from __future__ import annotations

import time
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
    ):
        res = client.get(f"/tenants/{tenant}/domains", headers=_auth(tenant))
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_id"] == tenant
    assert body["run_id"] == str(fake_run_id)
    rows = {row["domain"]: row for row in body["domains"]}
    assert rows["alpha.com"]["status"] == "pending"
    assert rows["beta.com"]["status"] == "completed"


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
        "apps.api.routes.domains.run_eval_sync",
        return_value={"ok": True, "run_id": "x", "count": 1, "error": None},
    ):
        start = client.post(
            f"/tenants/{tenant}/domains/evaluate",
            headers=_auth(tenant),
            json={"domains": ["one.com"]},
        )
        assert start.status_code == 202
        job_id = start.json()["job_id"]

        status = client.get(f"/tenants/{tenant}/jobs/{job_id}", headers=_auth(tenant))
        assert status.status_code == 200
        if status.json()["status"] == "running":
            time.sleep(0.05)
            status = client.get(f"/tenants/{tenant}/jobs/{job_id}", headers=_auth(tenant))
        assert status.json()["status"] in {"completed", "running"}
