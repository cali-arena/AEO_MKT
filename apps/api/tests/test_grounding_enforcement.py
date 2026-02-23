"""Tests proving hard grounding enforcement. No network; fake LLM + deterministic."""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.schemas.responses import RetrieveCandidate, RetrieveDebug, RetrieveDebugMerge, RetrieveDebugVector, RetrieveResponse

client = TestClient(app)

SECTION_TEXT = "storage and moving services for relocation."
EVIDENCE_QUOTE = "storage and moving services"


def _make_candidates():
    return [
        RetrieveCandidate(
            section_id="sec_1",
            merged_score=0.9,
            vector_score=0.8,
            bm25_score=0.7,
            rerank_score=0.9,
            rerank_reasons=[],
            url="https://example.com",
            version_hash="vh1",
            snippet=SECTION_TEXT,
        )
    ]


def _mock_retrieve():
    return RetrieveResponse(
        candidates=_make_candidates(),
        debug=RetrieveDebug(
            tenant_id="x",
            vector=RetrieveDebugVector(requested_k=5, returned_k=1),
            bm25=RetrieveDebugVector(requested_k=5, returned_k=1),
            merge=RetrieveDebugMerge(weights={}, deduped_count=0, final_k=1),
        ),
    )


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": SECTION_TEXT, "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"ANSWER_SOFT_GROUNDING": "false"})
def test_empty_evidence_ids_refused(mock_retrieve, mock_section, mock_insert) -> None:
    """LLM returns claim with empty evidence_ids → refused, unsupported text not in response."""
    mock_retrieve.return_value = _mock_retrieve()

    def fake_llm(prompt, evidence_items):
        return json.dumps({
            "answer": "Unsupported claim without evidence.",
            "claims": [{"text": "Unsupported claim without evidence.", "evidence_ids": [], "confidence": 0.9}],
        })

    with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
        mock_llm.return_value = MagicMock(generate=fake_llm)
        resp = client.post("/answer", json={"query": "moving"}, headers={"Authorization": "Bearer tenant:t"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is True
    assert data["refusal_reason"] == "empty_evidence_ids"
    assert data["answer"] == ""
    assert len(data["claims"]) == 0
    assert "Unsupported claim without evidence." not in (data["answer"] or "")


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": SECTION_TEXT, "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"ANSWER_SOFT_GROUNDING": "false"})
def test_nonexistent_evidence_id_refused(mock_retrieve, mock_section, mock_insert) -> None:
    """LLM returns claim with invented evidence_id → refused, unsupported text not in response."""
    mock_retrieve.return_value = _mock_retrieve()

    def fake_llm(prompt, evidence_items):
        return json.dumps({
            "answer": "Invented citation claim.",
            "claims": [{"text": "Invented citation claim.", "evidence_ids": ["nonexistent-evid-123"], "confidence": 0.9}],
        })

    with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
        mock_llm.return_value = MagicMock(generate=fake_llm)
        resp = client.post("/answer", json={"query": "moving"}, headers={"Authorization": "Bearer tenant:t"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is True
    assert data["refusal_reason"] == "invalid_evidence_id"
    assert data["answer"] == ""
    assert len(data["claims"]) == 0
    assert "Invented citation claim." not in (data["answer"] or "")


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": SECTION_TEXT, "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"ANSWER_SOFT_GROUNDING": "false", "GROUNDING_MIN_OVERLAP": "0.3"})
def test_low_overlap_refused(mock_retrieve, mock_section, mock_insert) -> None:
    """LLM returns claim whose text does not overlap quote_span → refused, hallucinated text not in response."""
    mock_retrieve.return_value = _mock_retrieve()

    def fake_llm(prompt, evidence_items):
        eids = [e["evidence_id"] for e in evidence_items]
        return json.dumps({
            "answer": "Contradiction hallucination xyz.",
            "claims": [
                {"text": "Contradiction hallucination xyz.", "evidence_ids": eids[:1], "confidence": 0.9},
            ],
        })

    with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
        mock_llm.return_value = MagicMock(generate=fake_llm)
        resp = client.post("/answer", json={"query": "moving"}, headers={"Authorization": "Bearer tenant:t"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is True
    assert data["refusal_reason"] == "low_overlap"
    assert data["answer"] == ""
    assert len(data["claims"]) == 0
    assert "Contradiction hallucination xyz." not in (data["answer"] or "")


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": SECTION_TEXT, "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"ANSWER_SOFT_GROUNDING": "false"})
def test_valid_claim_with_matching_quote_span_passes(mock_retrieve, mock_section, mock_insert) -> None:
    """Valid claim whose text overlaps quote_span passes and is returned."""
    mock_retrieve.return_value = _mock_retrieve()

    def fake_llm(prompt, evidence_items):
        eids = [e["evidence_id"] for e in evidence_items]
        return json.dumps({
            "answer": "Storage and moving services.",
            "claims": [
                {"text": "storage and moving services", "evidence_ids": eids[:1], "confidence": 0.9},
            ],
        })

    with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
        mock_llm.return_value = MagicMock(generate=fake_llm)
        resp = client.post("/answer", json={"query": "moving"}, headers={"Authorization": "Bearer tenant:t"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is False
    assert data["refusal_reason"] is None
    assert len(data["claims"]) == 1
    assert data["claims"][0]["text"] == "storage and moving services"
    assert "storage and moving services" in data["answer"]
