"""Tests for domain status derivation: ui_status never DONE unless index + eval DONE; INDEXING/EVALUATING rules."""

from __future__ import annotations

from unittest.mock import patch

from apps.api.services.domain_status import derive_domain_status, get_domains_with_status


def test_derive_domain_status_never_done_unless_index_and_eval_done() -> None:
    """ui_status is NEVER DONE unless index_state is DONE and eval job is DONE."""
    # Index DONE but eval NONE -> INDEXING (no job so do not show EVALUATING/Running)
    assert derive_domain_status({"status": "DONE"}, None, domain="d1.com") == "INDEXING"
    # Index DONE, eval PENDING -> EVALUATING
    assert derive_domain_status({"status": "DONE"}, "PENDING", domain="d1.com") == "EVALUATING"
    # Index DONE, eval RUNNING -> EVALUATING
    assert derive_domain_status({"status": "DONE"}, "RUNNING", domain="d1.com") == "EVALUATING"
    # Index DONE, eval DONE -> DONE
    assert derive_domain_status({"status": "DONE"}, "DONE", domain="d1.com") == "DONE"
    # No index state -> UNINDEXED (not DONE)
    assert derive_domain_status(None, "DONE", domain="d1.com") == "UNINDEXED"
    # Index RUNNING -> INDEXING (not DONE)
    assert derive_domain_status({"status": "RUNNING"}, "DONE", domain="d1.com") == "INDEXING"


def test_derive_domain_status_indexing_when_index_running() -> None:
    """When index_state is RUNNING and eval not started, ui_status is INDEXING."""
    assert derive_domain_status({"status": "RUNNING"}, None) == "INDEXING"
    assert derive_domain_status({"status": "RUNNING"}, "NONE") == "INDEXING"
    assert derive_domain_status({"status": "PENDING"}, None) == "INDEXING"


def test_derive_domain_status_evaluating_when_index_done_eval_running() -> None:
    """When index DONE and eval RUNNING (or PENDING), ui_status is EVALUATING."""
    assert derive_domain_status({"status": "DONE"}, "RUNNING") == "EVALUATING"
    assert derive_domain_status({"status": "DONE"}, "PENDING") == "EVALUATING"
    assert derive_domain_status({"status": "DONE"}, "RUNNING", orchestrate_current_domain="d1.com", domain="d1.com") == "EVALUATING"


def test_derive_domain_status_failed() -> None:
    """Index FAILED or eval FAILED -> FAILED."""
    assert derive_domain_status({"status": "FAILED"}, None) == "FAILED"
    assert derive_domain_status({"status": "DONE"}, "FAILED") == "FAILED"


def test_get_domains_with_status_ui_status_never_done_unless_both_done() -> None:
    """get_domains_with_status returns ui_status DONE only when index DONE and eval DONE."""
    tenant = "tenant-ui-status"
    with (
        patch("apps.api.services.domain_status.list_eval_domains", return_value=["a.com", "b.com"]),
        patch(
            "apps.api.services.domain_status.get_domain_index_states_for_tenant",
            return_value={
                "a.com": {"status": "DONE", "last_indexed_at": None, "last_error": None},
                "b.com": {"status": "RUNNING", "last_indexed_at": None, "last_error": None},
            },
        ),
        patch(
            "apps.api.services.domain_status.get_latest_domain_job_statuses",
            return_value={"a.com": "DONE", "b.com": "NONE"},
        ),
        patch("apps.api.services.domain_status.get_running_orchestrate_current_domain", return_value=None),
    ):
        rows = get_domains_with_status(tenant)
    by_domain = {r["domain"]: r for r in rows}
    assert by_domain["a.com"]["ui_status"] == "DONE"
    assert by_domain["a.com"]["index_status"] == "DONE"
    assert by_domain["a.com"]["eval_status"] == "DONE"
    assert by_domain["b.com"]["ui_status"] == "INDEXING"
    assert by_domain["b.com"]["index_status"] == "RUNNING"
    # b.com has no eval run -> INDEXING (index in progress), never DONE
    assert by_domain["b.com"]["eval_status"] == "NONE"
