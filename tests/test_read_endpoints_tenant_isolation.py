"""Read endpoints tenant isolation: eval runs/results, monitor events.

Create eval data for tenant A and B, call endpoints with auth tenant A => sees A only.
Call with tenant B => sees B only. No cross-tenant leakage.
Uses mock auth (Authorization: Bearer tenant:<id>) as in existing fixtures.
"""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.schemas.eval import EvalResultCreate
from apps.api.services.repo import (
    create_eval_run,
    create_monitor_event,
    insert_eval_results_bulk,
)
from apps.api.tests.conftest import requires_db

TENANT_A = "tenant_read_iso_a"
TENANT_B = "tenant_read_iso_b"

client = TestClient(app)


def _make_result(
    query_id: str,
    domain: str,
    query_text: str,
    *,
    refused: bool = False,
) -> EvalResultCreate:
    return EvalResultCreate(
        query_id=query_id,
        domain=domain,
        query_text=query_text,
        refused=refused,
        refusal_reason=None,
        mention_ok=True,
        citation_ok=True,
        attribution_ok=True,
        hallucination_flag=False,
        evidence_count=1,
        avg_confidence=0.9,
        top_cited_urls=None,
        answer_preview="preview",
    )


@pytest.fixture
def eval_data_both_tenants():
    """Create eval runs + results for tenant A and B. Returns run ids."""
    run_a = create_eval_run(
        TENANT_A,
        crawl_policy_version="p1",
        ac_version_hash="ac1",
        ec_version_hash="ec1",
        git_sha=None,
    )
    run_b = create_eval_run(
        TENANT_B,
        crawl_policy_version="p1",
        ac_version_hash="ac1",
        ec_version_hash="ec1",
        git_sha=None,
    )
    insert_eval_results_bulk(
        TENANT_A,
        run_a.id,
        [_make_result("q_a1", "dom_a", "Query A1"), _make_result("q_a2", "dom_a", "Query A2")],
    )
    insert_eval_results_bulk(
        TENANT_B,
        run_b.id,
        [_make_result("q_b1", "dom_b", "Query B1")],
    )
    create_monitor_event(TENANT_A, event_type="leakage_fail", severity="high", details_json={"reason": "A fail"})
    create_monitor_event(TENANT_B, event_type="leakage_fail", severity="medium", details_json={"reason": "B fail"})
    return {"run_a_id": run_a.id, "run_b_id": run_b.id}


@requires_db
def test_eval_runs_tenant_a_sees_only_a(eval_data_both_tenants) -> None:
    """Tenant A auth => /eval/runs returns only A's runs."""
    resp = client.get("/eval/runs", headers={"Authorization": f"Bearer tenant:{TENANT_A}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == TENANT_A
    run_ids = [r["run_id"] for r in data["runs"]]
    assert str(eval_data_both_tenants["run_a_id"]) in run_ids
    assert str(eval_data_both_tenants["run_b_id"]) not in run_ids


@requires_db
def test_eval_runs_tenant_b_sees_only_b(eval_data_both_tenants) -> None:
    """Tenant B auth => /eval/runs returns only B's runs."""
    resp = client.get("/eval/runs", headers={"Authorization": f"Bearer tenant:{TENANT_B}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == TENANT_B
    run_ids = [r["run_id"] for r in data["runs"]]
    assert str(eval_data_both_tenants["run_b_id"]) in run_ids
    assert str(eval_data_both_tenants["run_a_id"]) not in run_ids


@requires_db
def test_eval_results_tenant_a_sees_a_results(eval_data_both_tenants) -> None:
    """Tenant A auth => /eval/runs/{run_a_id}/results returns A's results."""
    run_a_id = eval_data_both_tenants["run_a_id"]
    resp = client.get(
        f"/eval/runs/{run_a_id}/results",
        headers={"Authorization": f"Bearer tenant:{TENANT_A}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == TENANT_A
    assert len(data["results"]) == 2
    assert all(r["domain"] == "dom_a" for r in data["results"])


@requires_db
def test_eval_results_tenant_b_cannot_see_a_results(eval_data_both_tenants) -> None:
    """Tenant B auth => /eval/runs/{run_a_id}/results returns empty (no cross-leak)."""
    run_a_id = eval_data_both_tenants["run_a_id"]
    resp = client.get(
        f"/eval/runs/{run_a_id}/results",
        headers={"Authorization": f"Bearer tenant:{TENANT_B}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == TENANT_B
    assert len(data["results"]) == 0


@requires_db
def test_eval_metrics_latest_tenant_a(eval_data_both_tenants) -> None:
    """Tenant A auth => /eval/metrics/latest returns A's metrics."""
    resp = client.get("/eval/metrics/latest", headers={"Authorization": f"Bearer tenant:{TENANT_A}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == str(eval_data_both_tenants["run_a_id"])


@requires_db
def test_eval_metrics_latest_tenant_b(eval_data_both_tenants) -> None:
    """Tenant B auth => /eval/metrics/latest returns B's metrics."""
    resp = client.get("/eval/metrics/latest", headers={"Authorization": f"Bearer tenant:{TENANT_B}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == str(eval_data_both_tenants["run_b_id"])


@requires_db
def test_monitor_events_tenant_a_sees_only_a(eval_data_both_tenants) -> None:
    """Tenant A auth => /monitor/events returns only A's events."""
    resp = client.get("/monitor/events", headers={"Authorization": f"Bearer tenant:{TENANT_A}"})
    assert resp.status_code == 200
    events = resp.json()
    assert all(e["tenant_id"] == TENANT_A for e in events)


@requires_db
def test_monitor_events_tenant_b_sees_only_b(eval_data_both_tenants) -> None:
    """Tenant B auth => /monitor/events returns only B's events."""
    resp = client.get("/monitor/events", headers={"Authorization": f"Bearer tenant:{TENANT_B}"})
    assert resp.status_code == 200
    events = resp.json()
    assert all(e["tenant_id"] == TENANT_B for e in events)


@requires_db
def test_monitor_leakage_latest_tenant_a(eval_data_both_tenants) -> None:
    """Tenant A auth => /monitor/leakage/latest returns A's leakage status."""
    resp = client.get("/monitor/leakage/latest", headers={"Authorization": f"Bearer tenant:{TENANT_A}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == TENANT_A
    assert data["ok"] is False
    assert data["details_json"] == {"reason": "A fail"}


@requires_db
def test_monitor_leakage_latest_tenant_b(eval_data_both_tenants) -> None:
    """Tenant B auth => /monitor/leakage/latest returns B's leakage status."""
    resp = client.get("/monitor/leakage/latest", headers={"Authorization": f"Bearer tenant:{TENANT_B}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == TENANT_B
    assert data["ok"] is False
    assert data["details_json"] == {"reason": "B fail"}
