"""Integration tests for eval metrics endpoint. No network calls."""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.schemas.eval import EvalResultCreate
from apps.api.services.repo import create_eval_run, insert_eval_results_bulk
from apps.api.tests.conftest import requires_db

TEST_TENANT = "tenant_eval_metrics_integration"
client = TestClient(app)


def _make_result(
    query_id: str,
    domain: str,
    query_text: str,
    *,
    mention_ok: bool = True,
    citation_ok: bool = True,
    attribution_ok: bool = True,
    hallucination_flag: bool = False,
) -> EvalResultCreate:
    return EvalResultCreate(
        query_id=query_id,
        domain=domain,
        query_text=query_text,
        refused=False,
        refusal_reason=None,
        mention_ok=mention_ok,
        citation_ok=citation_ok,
        attribution_ok=attribution_ok,
        hallucination_flag=hallucination_flag,
        evidence_count=1,
        avg_confidence=0.9,
        top_cited_urls=None,
        answer_preview="preview",
    )


@requires_db
def test_metrics_latest_returns_correct_rates_and_per_domain() -> None:
    """Create eval_run + 3 eval_results, query GET /eval/metrics/latest, assert rates and per-domain."""
    run = create_eval_run(
        TEST_TENANT,
        crawl_policy_version="test",
        ac_version_hash="ac1",
        ec_version_hash="ec1",
        git_sha=None,
    )
    results = [
        _make_result("q1", "dom_a", "Q1", mention_ok=True, citation_ok=True, attribution_ok=True, hallucination_flag=False),
        _make_result("q2", "dom_a", "Q2", mention_ok=True, citation_ok=False, attribution_ok=False, hallucination_flag=True),
        _make_result("q3", "dom_b", "Q3", mention_ok=False, citation_ok=False, attribution_ok=False, hallucination_flag=False),
    ]
    insert_eval_results_bulk(TEST_TENANT, run.id, results)

    resp = client.get(
        "/eval/metrics/latest",
        headers={"Authorization": f"Bearer tenant:{TEST_TENANT}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["run_id"] == str(run.id)

    # Overall: 2/3 mention, 1/3 citation, 1/3 attribution, 1/3 hallucination
    overall = data["overall"]
    assert abs(overall["mention_rate"] - 2 / 3) < 1e-6
    assert abs(overall["citation_rate"] - 1 / 3) < 1e-6
    assert abs(overall["attribution_rate"] - 1 / 3) < 1e-6
    assert abs(overall["hallucination_rate"] - 1 / 3) < 1e-6

    # Per-domain: dom_a (2 rows), dom_b (1 row)
    per_domain = data["per_domain"]
    assert "dom_a" in per_domain
    assert "dom_b" in per_domain

    dom_a = per_domain["dom_a"]
    assert dom_a["mention_rate"] == 1.0
    assert dom_a["citation_rate"] == 0.5
    assert dom_a["attribution_rate"] == 0.5
    assert dom_a["hallucination_rate"] == 0.5

    dom_b = per_domain["dom_b"]
    assert dom_b["mention_rate"] == 0.0
    assert dom_b["citation_rate"] == 0.0
    assert dom_b["attribution_rate"] == 0.0
    assert dom_b["hallucination_rate"] == 0.0
