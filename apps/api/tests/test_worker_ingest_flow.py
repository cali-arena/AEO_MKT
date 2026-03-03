from apps.api import worker


def test_process_job_runs_ingest_before_eval(monkeypatch):
    calls: list[str] = []
    finished: dict = {}

    def _fake_ingest(tenant_id: str, domain: str):
        calls.append(f"ingest:{tenant_id}:{domain}")
        return {"raw_page_inserted": 1}

    def _fake_eval(tenant_id: str, domain: str | None):
        calls.append(f"eval:{tenant_id}:{domain}")
        return {"ok": True, "run_id": "run-1"}

    def _fake_finish(job_id: str, **kwargs):
        finished["job_id"] = job_id
        finished.update(kwargs)

    monkeypatch.setattr(worker, "ingest_domain_sync", _fake_ingest)
    monkeypatch.setattr(worker, "run_eval_sync", _fake_eval)
    monkeypatch.setattr(worker, "finish_domain_eval_job", _fake_finish)

    worker._process_job(  # noqa: SLF001
        {"id": "job-1", "tenant_id": "tenant-1", "domains": ["example.com"], "total": 1},
        worker_id="w-1",
    )

    assert calls == ["ingest:tenant-1:example.com", "eval:tenant-1:example.com"]
    assert finished["status"] == "DONE"
    assert finished["completed"] == 1
    assert finished["run_id"] == "run-1"


def test_process_job_marks_failed_when_ingest_fails(monkeypatch):
    finished: dict = {}
    eval_called = {"value": False}

    def _fail_ingest(_tenant_id: str, _domain: str):
        raise RuntimeError("ingest boom")

    def _fake_eval(_tenant_id: str, _domain: str | None):
        eval_called["value"] = True
        return {"ok": True, "run_id": "run-1"}

    def _fake_finish(job_id: str, **kwargs):
        finished["job_id"] = job_id
        finished.update(kwargs)

    monkeypatch.setattr(worker, "ingest_domain_sync", _fail_ingest)
    monkeypatch.setattr(worker, "run_eval_sync", _fake_eval)
    monkeypatch.setattr(worker, "finish_domain_eval_job", _fake_finish)

    worker._process_job(  # noqa: SLF001
        {"id": "job-2", "tenant_id": "tenant-1", "domains": ["example.com"], "total": 1},
        worker_id="w-1",
    )

    assert eval_called["value"] is False
    assert finished["status"] == "FAILED"
    assert finished["completed"] == 0
    assert "ingest boom" in (finished.get("error_message") or "")
