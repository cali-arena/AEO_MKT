"""Tests for cron scripts: verify eval_nightly and leakage_nightly insert DB rows.

Monkeypatches API calls; no real network. Requires Postgres.
"""

import pytest

from apps.api.services.repo import (
    get_eval_results,
    list_eval_runs,
    list_monitor_events,
)
from apps.api.tests.conftest import requires_db

TENANT_EVAL = "tenant_nightly_eval"
TENANT_LEAK = "tenant_nightly_leak"


def _mock_answer_ok(row: dict) -> dict:
    """Deterministic /answer-like response for eval harness."""
    return {
        **row,
        "refused": False,
        "refusal_reason": None,
        "answer": "Test answer",
        "claims": [{"evidence_ids": ["e1"], "text": "claim"}],
        "citations": {"e1": {"url": "https://example.com"}},
        "evidence_ids": ["e1"],
        "scores": {"top_score": 0.9},
        "run_meta": None,
    }


@requires_db
def test_eval_nightly_inserts_eval_run_and_results(monkeypatch) -> None:
    """Run eval_nightly with mocked /answer; assert eval_run + eval_result inserted."""
    def mock_load_queries(tenant_id: str):
        if tenant_id == TENANT_EVAL:
            return [
                {"query_id": "qn1", "domain": "d1", "query": "Q1", "tenant_id": TENANT_EVAL},
                {"query_id": "qn2", "domain": "d1", "query": "Q2", "tenant_id": TENANT_EVAL},
            ]
        return []

    def mock_call_answer(session, base_url, row, tenant_id, timeout):
        return _mock_answer_ok(row)

    monkeypatch.setattr("cron.config.config", "TENANTS", [TENANT_EVAL])
    monkeypatch.setattr("cron.eval_nightly._load_queries", mock_load_queries)
    monkeypatch.setattr("cron.eval_nightly._call_answer", mock_call_answer)

    from cron.eval_nightly import main

    exit_code = main()
    assert exit_code == 0

    runs = list_eval_runs(TENANT_EVAL, limit=5)
    assert len(runs) >= 1
    run = runs[0]
    assert run.crawl_policy_version == "nightly"

    results = get_eval_results(TENANT_EVAL, run.id)
    assert len(results) == 2
    assert all(r.mention_ok for r in results)


@requires_db
def test_leakage_nightly_pass_inserts_monitor_event(monkeypatch) -> None:
    """Run leakage_nightly with mocked retrieve returning empty; assert leakage_pass inserted."""
    def mock_load_foreign(tenant_id: str):
        if tenant_id == TENANT_LEAK:
            return [{"query_id": "qf1", "query": "foreign Q", "tenant_id": "other_tenant"}]
        return []

    def mock_retrieve_ac(*_args, **_kwargs):
        return ([], True)  # no candidates, ok

    monkeypatch.setattr("cron.config.config", "TENANTS", [TENANT_LEAK])
    monkeypatch.setattr("cron.leakage_nightly._load_foreign_queries", mock_load_foreign)
    monkeypatch.setattr("cron.leakage_nightly._call_retrieve_ac", mock_retrieve_ac)

    from cron.leakage_nightly import main

    exit_code = main()
    assert exit_code == 0

    events = list_monitor_events(TENANT_LEAK, event_type="leakage_pass", limit=1)
    assert len(events) >= 1
    assert events[0].event_type == "leakage_pass"
    assert events[0].details_json is not None
    assert events[0].details_json.get("leaks") == 0


@requires_db
def test_leakage_nightly_fail_inserts_monitor_event(monkeypatch) -> None:
    """Run leakage_nightly with mocked retrieve returning candidates; assert leakage_fail inserted."""
    tenant_fail = "tenant_nightly_leak_fail"

    def mock_load_foreign(tenant_id: str):
        if tenant_id == tenant_fail:
            return [{"query_id": "qf1", "query": "foreign Q", "tenant_id": "other"}]
        return []

    def mock_retrieve_ac(*_args, **_kwargs):
        return ([{"section_id": "s1", "url": "https://x.com"}], True)

    monkeypatch.setattr("cron.config.config", "TENANTS", [tenant_fail])
    monkeypatch.setattr("cron.leakage_nightly._load_foreign_queries", mock_load_foreign)
    monkeypatch.setattr("cron.leakage_nightly._call_retrieve_ac", mock_retrieve_ac)

    from cron.leakage_nightly import main

    exit_code = main()
    assert exit_code == 1

    events = list_monitor_events(tenant_fail, event_type="leakage_fail", limit=1)
    assert len(events) >= 1
    assert events[0].event_type == "leakage_fail"
    assert events[0].severity == "high"
    det = events[0].details_json
    assert det is not None
    assert det.get("leak_count", 0) >= 1
    assert "offending" in det
