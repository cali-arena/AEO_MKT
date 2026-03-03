"""Tests for Way 1 orchestrate job: sequential ensure_ingested -> ingest -> eval per domain."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.api import worker


def test_run_orchestrate_triggers_ingest_then_eval_for_unindexed_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """If domain is UNINDEXED, orchestration runs ingest inline then eval sequentially (Way 1)."""
    ensure_calls: list[tuple[str, str]] = []
    ingest_run_calls: list[str] = []
    eval_calls: list[tuple[str, str]] = []
    finish_calls: list[dict] = []

    def _ensure(tenant_id: str, domain: str, *, reason=None):
        ensure_calls.append((tenant_id, domain))
        return {
            "status": "PENDING",
            "desired": {},
            "state": {},
            "ingest_job_id": "ingest-1",
            "already_enqueued": False,
        }

    def _run_ingest(job_id: str):
        ingest_run_calls.append(job_id)

    def _get_ingest(job_id: str):
        return {"id": job_id, "tenant_id": "t1", "domain": "d1.com", "status": "DONE"}

    def _eval(tenant_id: str, domain: str):
        eval_calls.append((tenant_id, domain))
        return {"ok": True, "run_id": "r1"}

    def _finish(job_id: str, status: str, **kwargs):
        finish_calls.append({"job_id": job_id, "status": status, **kwargs})

    job = {
        "id": "orch-1",
        "tenant_id": "t1",
        "domains": ["d1.com"],
        "desired_by_domain": {"d1.com": {"ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"}},
        "status": "RUNNING",
    }

    monkeypatch.setattr(worker, "get_domain_orchestrate_job", lambda jid: job if jid == "orch-1" else None)
    monkeypatch.setattr(worker, "ensure_ingested", _ensure)
    monkeypatch.setattr(worker, "run_domain_ingest_job", _run_ingest)
    monkeypatch.setattr(worker, "get_domain_ingest_job", _get_ingest)
    monkeypatch.setattr(worker, "run_eval_sync", _eval)
    monkeypatch.setattr(worker, "finish_domain_orchestrate_job", lambda jid, st, **kw: _finish(jid, st, **kw))
    monkeypatch.setattr(worker, "set_orchestrate_current_domain", MagicMock())
    monkeypatch.setattr(worker, "update_orchestrate_progress", MagicMock())

    worker.run_domain_orchestrate_job("orch-1")

    assert ensure_calls == [("t1", "d1.com")]
    assert ingest_run_calls == ["ingest-1"]
    assert eval_calls == [("t1", "d1.com")]
    assert len(finish_calls) == 1
    assert finish_calls[0]["status"] == "DONE"
    assert finish_calls[0].get("error_code") is None


def test_run_orchestrate_fails_domain_not_indexed_when_ingest_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """If ingest fails, orchestration fails with DOMAIN_NOT_INDEXED and eval does not run."""
    ensure_calls: list[tuple[str, str]] = []
    eval_called: list[str] = []
    finish_calls: list[dict] = []

    def _ensure(tenant_id: str, domain: str, *, reason=None):
        ensure_calls.append((tenant_id, domain))
        return {
            "status": "PENDING",
            "desired": {},
            "state": {},
            "ingest_job_id": "ingest-fail",
            "already_enqueued": False,
        }

    def _run_ingest(job_id: str):
        pass

    def _get_ingest(job_id: str):
        return {"id": job_id, "tenant_id": "t1", "domain": "d1.com", "status": "FAILED", "error_message": "crawl error"}

    def _eval(tenant_id: str, domain: str):
        eval_called.append(domain)
        return {"ok": True}

    def _finish(job_id: str, status: str, **kwargs):
        finish_calls.append({"job_id": job_id, "status": status, **kwargs})

    job = {
        "id": "orch-2",
        "tenant_id": "t1",
        "domains": ["d1.com"],
        "desired_by_domain": {"d1.com": {}},
        "status": "RUNNING",
    }

    monkeypatch.setattr(worker, "get_domain_orchestrate_job", lambda jid: job if jid == "orch-2" else None)
    monkeypatch.setattr(worker, "ensure_ingested", _ensure)
    monkeypatch.setattr(worker, "run_domain_ingest_job", _run_ingest)
    monkeypatch.setattr(worker, "get_domain_ingest_job", _get_ingest)
    monkeypatch.setattr(worker, "run_eval_sync", _eval)
    monkeypatch.setattr(worker, "finish_domain_orchestrate_job", lambda jid, st, **kw: _finish(jid, st, **kw))
    monkeypatch.setattr(worker, "set_orchestrate_current_domain", MagicMock())

    worker.run_domain_orchestrate_job("orch-2")

    assert ensure_calls == [("t1", "d1.com")]
    assert len(eval_called) == 0, "eval must not run when ingest failed"
    assert len(finish_calls) == 1
    assert finish_calls[0]["status"] == "FAILED"
    assert finish_calls[0].get("error_code") == "DOMAIN_NOT_INDEXED"
    assert "ingest failed" in str(finish_calls[0].get("error_message", "")).lower()
