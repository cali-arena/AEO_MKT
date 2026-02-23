"""Tests for /answer grounding: refused when no evidence, claims with evidence_ids when evidence present."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.schemas.responses import RetrieveCandidate, RetrieveDebug, RetrieveDebugMerge, RetrieveDebugVector, RetrieveResponse
from apps.api.tests.conftest import requires_db


client = TestClient(app)


def _post_answer(tenant_id: str, query: str = "test query"):
    return client.post(
        "/answer",
        json={"query": query},
        headers={"Authorization": f"Bearer tenant:{tenant_id}"},
    )


@patch("apps.api.services.answer.retrieve_ac")
def test_no_evidence_refused(mock_retrieve) -> None:
    """When /answer has no evidence, response must be refused=true, refusal_reason='no_evidence'."""
    mock_retrieve.return_value = RetrieveResponse(
        candidates=[],
        debug=RetrieveDebug(
            tenant_id="x",
            vector=RetrieveDebugVector(requested_k=5, returned_k=0),
            bm25=RetrieveDebugVector(requested_k=5, returned_k=0),
            merge=RetrieveDebugMerge(weights={}, deduped_count=0, final_k=0),
        ),
    )
    resp = _post_answer("tenant_no_evidence_xyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is True
    assert data["refusal_reason"] == "no_evidence"


@requires_db
def test_has_evidence_not_refused() -> None:
    """When retrieval returns candidates, answer creates evidence on-the-fly and returns claims with evidence_ids."""
    from apps.api.services.index_ac import index_ac
    from apps.api.services.repo import get_evidence_by_ids, insert_raw_page, insert_sections

    tenant_id = "tenant_has_evidence_xyz"
    url = "https://example.com/doc"
    pid = insert_raw_page(tenant_id, url, text="Doc content with evidence.")
    sections = [
        {"section_id": "ev_sec_1", "text": "Evidence section 1 content.", "version_hash": "vh1"},
        {"section_id": "ev_sec_2", "text": "Evidence section 2 content.", "version_hash": "vh2"},
    ]
    insert_sections(tenant_id, pid, sections)
    index_ac(tenant_id, [{"section_id": s["section_id"], "text": s["text"], "version_hash": s["version_hash"], "url": url} for s in sections])

    resp = _post_answer(tenant_id, "evidence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is False
    assert data["refusal_reason"] is None
    assert len(data["claims"]) >= 1
    for claim in data["claims"]:
        assert "evidence_ids" in claim
        assert len(claim["evidence_ids"]) >= 1
        ev_list = get_evidence_by_ids(tenant_id, claim["evidence_ids"])
        assert ev_list, "evidence must exist for claim"
        assert any(
            claim["text"] in (ev.get("quote_span") or "") for ev in ev_list
        ), f"claim.text must be substring of cited evidence.quote_span; claim={claim['text']!r}"
