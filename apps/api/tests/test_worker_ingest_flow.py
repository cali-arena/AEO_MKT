from apps.api import worker


def test_process_job_runs_eval_when_domain_indexed(monkeypatch):
    """Eval job runs eval only when domain_index_state is DONE and hashes match (2-phase, no ingest)."""
    calls: list[str] = []
    finished: dict = {}

    def _fake_eval(tenant_id: str, domain: str | None):
        calls.append(f"eval:{tenant_id}:{domain}")
        return {"ok": True, "run_id": "run-1"}

    def _fake_finish(job_id: str, **kwargs):
        finished["job_id"] = job_id
        finished.update(kwargs)

    # Index state DONE with matching hashes => assert passes, eval runs (no ingest)
    desired = {"ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"}
    state = {"status": "DONE", "ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"}
    monkeypatch.setattr(worker, "compute_desired_index_version", lambda t, d: desired)
    monkeypatch.setattr(worker, "get_domain_index_state", lambda t, d: state)
    monkeypatch.setattr(worker, "run_eval_sync", _fake_eval)
    monkeypatch.setattr(worker, "finish_domain_eval_job", _fake_finish)

    worker._process_job(  # noqa: SLF001
        {"id": "job-1", "tenant_id": "tenant-1", "domains": ["example.com"], "total": 1},
        worker_id="w-1",
    )

    assert calls == ["eval:tenant-1:example.com"]
    assert finished["status"] == "DONE"
    assert finished["completed"] == 1
    assert finished["run_id"] == "run-1"


def test_process_job_fails_with_domain_not_indexed_when_not_indexed(monkeypatch):
    """Eval job fails early with DOMAIN_NOT_INDEXED when domain is not indexed (no eval, no ingest)."""
    eval_called = {"value": False}
    finished: dict = {}

    def _fake_eval(_tenant_id: str, _domain: str | None):
        eval_called["value"] = True
        return {"ok": True, "run_id": "run-1"}

    def _fake_finish(job_id: str, **kwargs):
        finished["job_id"] = job_id
        finished.update(kwargs)

    # No index state => assert fails, job marked FAILED with error_code DOMAIN_NOT_INDEXED
    monkeypatch.setattr(worker, "compute_desired_index_version", lambda t, d: {"ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"})
    monkeypatch.setattr(worker, "get_domain_index_state", lambda t, d: None)
    monkeypatch.setattr(worker, "run_eval_sync", _fake_eval)
    monkeypatch.setattr(worker, "finish_domain_eval_job", _fake_finish)

    worker._process_job(  # noqa: SLF001
        {"id": "job-2", "tenant_id": "tenant-1", "domains": ["example.com"], "total": 1},
        worker_id="w-1",
    )

    assert eval_called["value"] is False
    assert finished["status"] == "FAILED"
    assert finished["completed"] == 0
    assert finished.get("error_code") == "DOMAIN_NOT_INDEXED"
    assert "not indexed" in (finished.get("error_message") or "").lower()


def test_process_job_fails_domain_not_indexed_when_running(monkeypatch):
    """Eval guard: index_state RUNNING => fail early with error_code DOMAIN_NOT_INDEXED."""
    desired = {"ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"}
    state = {"status": "RUNNING", "ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"}
    finished: dict = {}

    def _fake_finish(job_id: str, **kwargs):
        finished.update(kwargs)

    monkeypatch.setattr(worker, "compute_desired_index_version", lambda t, d: desired)
    monkeypatch.setattr(worker, "get_domain_index_state", lambda t, d: state)
    monkeypatch.setattr(worker, "finish_domain_eval_job", _fake_finish)

    worker._process_job(  # noqa: SLF001
        {"id": "job-3", "tenant_id": "tenant-1", "domains": ["example.com"], "total": 1},
        worker_id="w-1",
    )

    assert finished["status"] == "FAILED"
    assert finished.get("error_code") == "DOMAIN_NOT_INDEXED"
    assert "RUNNING" in (finished.get("error_message") or "")


def test_process_job_fails_domain_not_indexed_when_failed(monkeypatch):
    """Eval guard: index_state FAILED => fail early with error_code DOMAIN_NOT_INDEXED."""
    desired = {"ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"}
    state = {"status": "FAILED", "last_error": "crawl error", "ac_version_hash": "a", "ec_version_hash": "e", "crawl_policy_version": "c"}
    finished: dict = {}

    def _fake_finish(job_id: str, **kwargs):
        finished.update(kwargs)

    monkeypatch.setattr(worker, "compute_desired_index_version", lambda t, d: desired)
    monkeypatch.setattr(worker, "get_domain_index_state", lambda t, d: state)
    monkeypatch.setattr(worker, "finish_domain_eval_job", _fake_finish)

    worker._process_job(  # noqa: SLF001
        {"id": "job-4", "tenant_id": "tenant-1", "domains": ["example.com"], "total": 1},
        worker_id="w-1",
    )

    assert finished["status"] == "FAILED"
    assert finished.get("error_code") == "DOMAIN_NOT_INDEXED"
    assert "FAILED" in (finished.get("error_message") or "") or "crawl error" in (finished.get("error_message") or "")


def test_process_job_fails_domain_not_indexed_when_stale(monkeypatch):
    """Eval guard: index_state DONE but hashes mismatch (stale) => fail with DOMAIN_NOT_INDEXED."""
    desired = {"ac_version_hash": "a2", "ec_version_hash": "e2", "crawl_policy_version": "c2"}
    state = {"status": "DONE", "ac_version_hash": "a1", "ec_version_hash": "e1", "crawl_policy_version": "c1"}
    finished: dict = {}

    def _fake_finish(job_id: str, **kwargs):
        finished.update(kwargs)

    monkeypatch.setattr(worker, "compute_desired_index_version", lambda t, d: desired)
    monkeypatch.setattr(worker, "get_domain_index_state", lambda t, d: state)
    monkeypatch.setattr(worker, "finish_domain_eval_job", _fake_finish)

    worker._process_job(  # noqa: SLF001
        {"id": "job-5", "tenant_id": "tenant-1", "domains": ["example.com"], "total": 1},
        worker_id="w-1",
    )

    assert finished["status"] == "FAILED"
    assert finished.get("error_code") == "DOMAIN_NOT_INDEXED"
    assert "not up to date" in (finished.get("error_message") or "").lower() or "stale" in (finished.get("error_message") or "").lower()
