"""Tests for eval/monitor DB storage: eval_run, eval_result, monitor_event.

Proves Step 1 complete: create, insert, query with tenant isolation.
Uses existing test DB (DATABASE_URL); deterministic, no network.
"""

from datetime import date

import pytest

from apps.api.schemas.eval import EvalResultCreate
from apps.api.services.repo import (
    create_eval_run,
    create_monitor_event,
    get_eval_results,
    insert_eval_results_bulk,
    list_eval_runs,
    list_monitor_events,
)
from apps.api.tests.conftest import requires_db


TENANT_A = "tenant_eval_storage_a"
TENANT_B = "tenant_eval_storage_b"


def _make_result(
    query_id: str,
    domain: str,
    query_text: str,
    *,
    refused: bool = False,
    mention_ok: bool = True,
    citation_ok: bool = True,
    attribution_ok: bool = True,
    hallucination_flag: bool = False,
) -> EvalResultCreate:
    return EvalResultCreate(
        query_id=query_id,
        domain=domain,
        query_text=query_text,
        refused=refused,
        refusal_reason=None,
        mention_ok=mention_ok,
        citation_ok=citation_ok,
        attribution_ok=attribution_ok,
        hallucination_flag=hallucination_flag,
        evidence_count=1,
        avg_confidence=0.9,
        top_cited_urls=None,
        answer_preview="Answer preview",
    )


@requires_db
def test_insert_fake_run_and_results_roundtrip() -> None:
    """Create eval_run for tenant A, insert 3 eval_results (two domains), query by tenant+domain and date range."""
    run = create_eval_run(
        TENANT_A,
        crawl_policy_version="test",
        ac_version_hash="ac1",
        ec_version_hash="ec1",
        git_sha=None,
    )
    assert run.id is not None

    results = [
        _make_result("q1", "domain_x", "Query 1"),
        _make_result("q2", "domain_x", "Query 2"),
        _make_result("q3", "domain_y", "Query 3"),
    ]
    n = insert_eval_results_bulk(TENANT_A, run.id, results)
    assert n == 3

    # Query by tenant A + domain filter => correct count
    by_domain_x = get_eval_results(TENANT_A, run.id, domain="domain_x")
    assert len(by_domain_x) == 2

    by_domain_y = get_eval_results(TENANT_A, run.id, domain="domain_y")
    assert len(by_domain_y) == 1

    # Query by tenant A + date range (run created today) => correct count
    today = date.today()
    by_date = get_eval_results(TENANT_A, run.id, date_from=today, date_to=today)
    assert len(by_date) == 3


@requires_db
def test_tenant_isolation_eval_results() -> None:
    """Create run/results for tenant A; query as tenant B => returns 0."""
    run = create_eval_run(
        TENANT_A,
        crawl_policy_version="test",
        ac_version_hash="ac1",
        ec_version_hash="ec1",
    )
    insert_eval_results_bulk(TENANT_A, run.id, [_make_result("q1", "d1", "Q1")])

    # Query as tenant B => 0 results
    as_b = get_eval_results(TENANT_B, run.id)
    assert len(as_b) == 0

    # List runs as tenant B => 0
    runs_b = list_eval_runs(TENANT_B)
    assert len(runs_b) == 0


@requires_db
def test_monitor_event_roundtrip() -> None:
    """Insert monitor_event for tenant A; list as A => 1, list as B => 0."""
    create_monitor_event(TENANT_A, event_type="leakage_fail", severity="high", details_json={"reason": "test"})

    events_a = list_monitor_events(TENANT_A)
    assert len(events_a) >= 1
    assert events_a[0].tenant_id == TENANT_A
    assert events_a[0].event_type == "leakage_fail"
    assert events_a[0].severity == "high"

    events_b = list_monitor_events(TENANT_B)
    assert len(events_b) == 0
