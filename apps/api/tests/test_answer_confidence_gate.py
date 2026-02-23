"""Tests for /answer retrieval confidence gate (MIN_MERGED_SCORE)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.schemas.responses import RetrieveCandidate, RetrieveDebug, RetrieveDebugMerge, RetrieveDebugVector, RetrieveResponse

client = TestClient(app)


def _candidates(merged_score: float):
    return [
        RetrieveCandidate(
            section_id="sec_1",
            merged_score=merged_score,
            vector_score=0.5,
            bm25_score=0.5,
            rerank_score=merged_score,
            rerank_reasons=[],
            url="https://example.com",
            version_hash="vh1",
            snippet="Test.",
        )
    ]


@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"MIN_MERGED_SCORE": "0.35"})
def test_low_merged_score_refused(mock_retrieve) -> None:
    """When top merged_score < MIN_MERGED_SCORE, refuse with LOW_RETRIEVAL_CONFIDENCE."""
    mock_retrieve.return_value = RetrieveResponse(
        candidates=_candidates(0.2),
        debug=RetrieveDebug(
            tenant_id="x",
            vector=RetrieveDebugVector(requested_k=5, returned_k=1),
            bm25=RetrieveDebugVector(requested_k=5, returned_k=1),
            merge=RetrieveDebugMerge(weights={}, deduped_count=0, final_k=1),
        ),
    )

    resp = client.post("/answer", json={"query": "test"}, headers={"Authorization": "Bearer tenant:t_low"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is True
    assert data["refusal_reason"] == "LOW_RETRIEVAL_CONFIDENCE"
    assert data["citations"] == {} or len(data["citations"]) == 0
    assert data["claims"] == []
    assert data["answer"] == ""
    assert data["debug"] is not None
    assert data["debug"]["threshold"] == 0.35
    assert data["debug"]["top_score"] == 0.2


@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"MIN_MERGED_SCORE": "0.35"})
def test_at_threshold_passes(mock_retrieve) -> None:
    """When top merged_score == threshold, proceed (not refused)."""
    mock_retrieve.return_value = RetrieveResponse(
        candidates=_candidates(0.35),
        debug=RetrieveDebug(
            tenant_id="x",
            vector=RetrieveDebugVector(requested_k=5, returned_k=1),
            bm25=RetrieveDebugVector(requested_k=5, returned_k=1),
            merge=RetrieveDebugMerge(weights={}, deduped_count=0, final_k=1),
        ),
    )

    with patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test.", "version_hash": "vh1"}):
        with patch("apps.api.services.answer.insert_evidence"):
            with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
                import json

                def fake_gen(prompt, evidence_items):
                    eids = [e["evidence_id"] for e in evidence_items]
                    return json.dumps({"answer": "X", "claims": [{"text": "X", "evidence_ids": eids, "confidence": 0.9}]})

                mock_llm.return_value = type("M", (), {"generate": lambda s, p, e: fake_gen(p, e)})()
                resp = client.post("/answer", json={"query": "test"}, headers={"Authorization": "Bearer tenant:t_at"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is False
    assert data["debug"]["top_score"] == 0.35
    assert data["debug"]["threshold"] == 0.35


@patch("apps.api.services.answer.retrieve_ac")
def test_default_threshold_0_35(mock_retrieve) -> None:
    """Default MIN_MERGED_SCORE is 0.35."""
    mock_retrieve.return_value = RetrieveResponse(
        candidates=_candidates(0.3),
        debug=RetrieveDebug(
            tenant_id="x",
            vector=RetrieveDebugVector(requested_k=5, returned_k=1),
            bm25=RetrieveDebugVector(requested_k=5, returned_k=1),
            merge=RetrieveDebugMerge(weights={}, deduped_count=0, final_k=1),
        ),
    )

    resp = client.post("/answer", json={"query": "test"}, headers={"Authorization": "Bearer tenant:t_def"})

    assert resp.status_code == 200
    assert resp.json()["refused"] is True
    assert resp.json()["refusal_reason"] == "LOW_RETRIEVAL_CONFIDENCE"
    assert resp.json()["debug"]["threshold"] == 0.35
