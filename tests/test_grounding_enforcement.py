"""Strict grounding enforcement: unsupported claims must refuse.

Tests /answer with validate_answer(draft, evidence_map):
- missing evidence_ids => refused
- unknown evidence_id => refused
- non-overlapping claim => refused
- valid overlapping claim => allowed
"""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.schemas.responses import (
    RetrieveCandidate,
    RetrieveDebug,
    RetrieveDebugMerge,
    RetrieveDebugVector,
    RetrieveResponse,
)

client = TestClient(app)

SECTION_TEXT = "storage and moving services for relocation."


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
            vector=RetrieveDebugVector(requested_k=5, returned_k=1, min=0.8, max=0.9, top_scores=[0.9]),
            bm25=RetrieveDebugVector(requested_k=5, returned_k=1, min=0.7, max=0.7, top_scores=[0.7]),
            merge=RetrieveDebugMerge(weights={"vector": 0.6, "bm25": 0.4}, deduped_count=0, final_k=1),
        ),
    )


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": SECTION_TEXT, "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"ANSWER_SOFT_GROUNDING": "false"})
def test_missing_evidence_ids_refused(mock_retrieve, mock_section, mock_insert) -> None:
    """missing evidence_ids => refused."""
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


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": SECTION_TEXT, "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"ANSWER_SOFT_GROUNDING": "false"})
def test_unknown_evidence_id_refused(mock_retrieve, mock_section, mock_insert) -> None:
    """unknown evidence_id => refused."""
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


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": SECTION_TEXT, "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"ANSWER_SOFT_GROUNDING": "false", "GROUNDING_MIN_OVERLAP": "0.3"})
def test_non_overlapping_claim_refused(mock_retrieve, mock_section, mock_insert) -> None:
    """non-overlapping claim => refused."""
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


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": SECTION_TEXT, "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"ANSWER_SOFT_GROUNDING": "false"})
def test_valid_overlapping_claim_allowed(mock_retrieve, mock_section, mock_insert) -> None:
    """valid overlapping claim => allowed."""
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
    assert "storage" in data["answer"] and "moving" in data["answer"]
