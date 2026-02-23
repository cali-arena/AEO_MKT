"""Tests for /answer LLM JSON parsing and evidence_id validation."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.schemas.responses import RetrieveCandidate, RetrieveDebug, RetrieveDebugMerge, RetrieveDebugVector, RetrieveResponse

client = TestClient(app)


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
            snippet="Test content.",
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
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test content.", "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
def test_parse_success_returns_claims(
    mock_retrieve,
    mock_section,
    mock_insert,
) -> None:
    """When LLM returns valid JSON, answer and claims are returned."""
    mock_retrieve.return_value = _mock_retrieve()

    # Mock LLM to return valid AnswerDraft JSON (evidence_id will match what answer creates)
    def fake_generate(prompt, evidence_items):
        import json

        eids = [e["evidence_id"] for e in evidence_items]
        return json.dumps({
            "answer": "The answer is X.",
            "claims": [
                {"text": "Claim 1", "evidence_ids": eids[:1], "confidence": 0.9},
            ],
        })

    with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
        mock_llm.return_value = MagicMock(generate=fake_generate)

        resp = client.post(
            "/answer",
            json={"query": "test"},
            headers={"Authorization": "Bearer tenant:test_tenant"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is False
    assert data["refusal_reason"] is None
    assert data["answer"] == "Claim 1"
    assert len(data["claims"]) == 1
    assert data["claims"][0]["text"] == "Claim 1"
    assert len(data["claims"][0]["evidence_ids"]) == 1


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test content.", "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
def test_parse_failure_refused(
    mock_retrieve,
    mock_section,
    mock_insert,
) -> None:
    """When LLM returns invalid JSON, refuse with llm_parse_error."""
    mock_retrieve.return_value = _mock_retrieve()

    with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
        mock_llm.return_value = MagicMock(generate=lambda p, e: "This is not JSON at all")

        resp = client.post(
            "/answer",
            json={"query": "test"},
            headers={"Authorization": "Bearer tenant:test_tenant"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is True
    assert data["refusal_reason"] == "llm_parse_error"
    assert data["answer"] == ""
    assert data["claims"] == []


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test content.", "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
@patch.dict("os.environ", {"ANSWER_SOFT_GROUNDING": "false"})
def test_invalid_evidence_id_refused(
    mock_retrieve,
    mock_section,
    mock_insert,
) -> None:
    """When LLM returns claims with invented evidence_ids, refuse (strict mode: invalid_evidence_id)."""
    mock_retrieve.return_value = _mock_retrieve()

    with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
        mock_llm.return_value = MagicMock(
            generate=lambda p, e: '{"answer": "X", "claims": [{"text": "Fake", "evidence_ids": ["invented-id-123"], "confidence": 0.9}]}'
        )

        resp = client.post(
            "/answer",
            json={"query": "test"},
            headers={"Authorization": "Bearer tenant:test_tenant"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is True
    assert data["refusal_reason"] == "invalid_evidence_id"
    assert data["answer"] == ""
    assert data["claims"] == []


@patch("apps.api.services.answer.insert_evidence")
@patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test content.", "version_hash": "vh1"})
@patch("apps.api.services.answer.retrieve_ac")
def test_json_inside_markdown_code_block_parsed(
    mock_retrieve,
    mock_section,
    mock_insert,
) -> None:
    """JSON wrapped in ``` code block is extracted and parsed."""
    mock_retrieve.return_value = _mock_retrieve()

    def fake_generate(prompt, evidence_items):
        import json

        eids = [e["evidence_id"] for e in evidence_items]
        inner = json.dumps({"answer": "From block.", "claims": [{"text": "C", "evidence_ids": eids, "confidence": 0.8}]})
        return f"```json\n{inner}\n```"

    with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
        mock_llm.return_value = MagicMock(generate=fake_generate)

        resp = client.post(
            "/answer",
            json={"query": "test"},
            headers={"Authorization": "Bearer tenant:test_tenant"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is False
    assert data["answer"] == "C"
