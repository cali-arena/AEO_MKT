"""Tests that API responses contain only contract-frozen fields."""

import os
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.schemas.responses import (
    Claim,
    RetrieveCandidate,
    RetrieveDebug,
    RetrieveDebugMerge,
    RetrieveDebugVector,
    RetrieveResponse,
)
from apps.api.tests.conftest import requires_db

client = TestClient(app)

# Frozen field sets
RETRIEVE_CANDIDATE_FIELDS = {"section_id", "merged_score", "vector_score", "bm25_score", "rerank_score", "rerank_reasons", "url", "version_hash", "snippet"}
RETRIEVE_DEBUG_VECTOR_FIELDS = {"requested_k", "returned_k", "min", "max", "top_scores"}
RETRIEVE_DEBUG_MERGE_FIELDS = {"weights", "deduped_count", "final_k"}
RETRIEVE_DEBUG_FIELDS = {"tenant_id", "vector", "bm25", "merge"}
EC_MENTION_FIELDS = {"section_id", "start_offset", "end_offset", "quote_span", "url"}
RETRIEVE_EC_CANDIDATE_FIELDS = {"entity_id", "score", "canonical_name", "entity_type", "mentions"}
RETRIEVE_EC_DEBUG_FIELDS = {"tenant_id", "vector", "entity_count"}
RETRIEVE_EC_RESPONSE_FIELDS = {"entities", "debug"}
CLAIM_FIELDS = {"text", "evidence_ids", "confidence"}
CITATION_FIELDS = {"url", "section_id", "quote_span"}
ANSWER_DEBUG_FIELDS = {"threshold", "top_score"}
ANSWER_RESPONSE_FIELDS = {"answer", "claims", "citations", "debug", "refused", "refusal_reason"}


@patch("apps.api.services.retrieve.execute_ec_retrieval", return_value=[])
def test_retrieve_ec_response_shape(mock_execute) -> None:
    """/retrieve/ec response has only entities and debug. Debug: fixed keys (tenant_id, vector, entity_count). No DB/network."""
    os.environ.setdefault("ENV", "test")
    resp = client.post(
        "/retrieve/ec",
        json={"query": "Dallas", "k": 5, "n": 3},
        headers={"Authorization": "Bearer tenant:contract_test"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert set(data) == RETRIEVE_EC_RESPONSE_FIELDS, f"Top-level keys must be exactly {RETRIEVE_EC_RESPONSE_FIELDS}"
    assert "entities" in data
    assert "debug" in data
    assert isinstance(data["entities"], list)

    debug = data["debug"]
    assert set(debug) == RETRIEVE_EC_DEBUG_FIELDS, f"debug keys must be exactly {RETRIEVE_EC_DEBUG_FIELDS}"
    assert isinstance(debug["tenant_id"], str)
    assert isinstance(debug["vector"], bool)
    assert isinstance(debug["entity_count"], int)
    # Empty entities case: fixed values
    assert len(data["entities"]) == 0
    assert debug["entity_count"] == 0
    assert debug["vector"] is True

    for ent in data["entities"]:
        assert set(ent) == RETRIEVE_EC_CANDIDATE_FIELDS
        for m in ent.get("mentions", []):
            assert set(m) == EC_MENTION_FIELDS


@patch("apps.api.services.retrieve.get_urls_for_section_ids")
@patch("apps.api.services.retrieve.get_entity_mentions_for_entities")
@patch("apps.api.services.retrieve.get_entities_by_ids")
@patch("apps.api.services.retrieve.execute_ec_retrieval")
def test_retrieve_ec_response_shape_with_results(
    mock_execute,
    mock_entities,
    mock_mentions,
    mock_urls,
) -> None:
    """/retrieve/ec with mocked results returns entity-level shape."""
    mock_execute.return_value = [("ent_abc123", 0.5)]
    mock_entities.return_value = {"ent_abc123": {"entity_id": "ent_abc123", "canonical_name": "Dallas, TX", "entity_type": "LOC"}}
    mock_mentions.return_value = {
        "ent_abc123": [
            {"section_id": "sec_1", "start_offset": 10, "end_offset": 18, "quote_span": "Dallas, TX"},
        ],
    }
    mock_urls.return_value = {"sec_1": "https://example.com/page"}

    resp = client.post(
        "/retrieve/ec",
        json={"query": "Dallas", "k": 5, "n": 3},
        headers={"Authorization": "Bearer tenant:contract_test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == RETRIEVE_EC_RESPONSE_FIELDS
    assert len(data["entities"]) == 1
    ent = data["entities"][0]
    assert set(ent) == RETRIEVE_EC_CANDIDATE_FIELDS
    assert ent["entity_id"] == "ent_abc123"
    assert ent["canonical_name"] == "Dallas, TX"
    assert len(ent["mentions"]) == 1
    m = ent["mentions"][0]
    assert set(m) == EC_MENTION_FIELDS
    assert m["section_id"] == "sec_1"
    assert m["quote_span"] == "Dallas, TX"
    assert m["url"] == "https://example.com/page"

    # debug: fixed keys, stable when entities present
    debug = data["debug"]
    assert set(debug) == RETRIEVE_EC_DEBUG_FIELDS
    assert isinstance(debug["tenant_id"], str)
    assert debug["vector"] is True
    assert debug["entity_count"] == 1


@patch("apps.api.services.retrieve.retrieve_ac_bm25", return_value=[])
@patch("apps.api.services.retrieve.execute_ac_retrieval", return_value=[])
def test_retrieve_ac_response_shape(mock_vec, mock_bm25) -> None:
    """/retrieve/ac response has only candidates[].section_id/score/url/version_hash/snippet and debug. No DB/network."""
    os.environ.setdefault("ENV", "test")
    resp = client.post(
        "/retrieve/ac",
        json={"query": "moving", "k": 5},
        headers={"Authorization": "Bearer tenant:contract_test"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "candidates" in data
    assert "debug" in data
    assert isinstance(data["candidates"], list)
    assert set(data) <= {"candidates", "debug"}, f"Unexpected top-level keys: {set(data) - {'candidates', 'debug'}}"

    for c in data["candidates"]:
        assert set(c) == RETRIEVE_CANDIDATE_FIELDS, f"candidate has extra keys: {set(c) - RETRIEVE_CANDIDATE_FIELDS}"

    assert "debug" in data, "debug must always be present"
    debug = data["debug"]
    assert set(debug) == RETRIEVE_DEBUG_FIELDS, f"debug has extra keys: {set(debug) - RETRIEVE_DEBUG_FIELDS}"

    # debug.vector and debug.bm25: fixed keys; empty channel => returned_k=0, min=0, max=0, top_scores=[]
    for branch in ("vector", "bm25"):
        dv = debug[branch]
        assert set(dv) == RETRIEVE_DEBUG_VECTOR_FIELDS, f"debug.{branch} has wrong keys: {set(dv) ^ RETRIEVE_DEBUG_VECTOR_FIELDS}"
        assert isinstance(dv["requested_k"], int)
        assert isinstance(dv["returned_k"], int)
        assert isinstance(dv["min"], (int, float))
        assert isinstance(dv["max"], (int, float))
        assert isinstance(dv["top_scores"], list) and len(dv["top_scores"]) <= 5
        # Empty channel (mocked): returned_k=0, min=0, max=0, top_scores=[]
        if dv["returned_k"] == 0:
            assert dv["min"] == 0
            assert dv["max"] == 0
            assert dv["top_scores"] == []
    # debug.merge: weights, deduped_count, final_k
    merge = debug["merge"]
    assert set(merge) == RETRIEVE_DEBUG_MERGE_FIELDS, f"debug.merge has wrong keys: {set(merge) ^ RETRIEVE_DEBUG_MERGE_FIELDS}"


@patch("apps.api.services.answer.retrieve_ac")
def test_answer_response_shape_no_evidence(mock_retrieve) -> None:
    """/answer response has answer, claims, citations, refused, refusal_reason."""
    mock_retrieve.return_value = RetrieveResponse(
        candidates=[],
        debug=RetrieveDebug(
            tenant_id="x",
            vector=RetrieveDebugVector(requested_k=5, returned_k=0, min=0, max=0, top_scores=[]),
            bm25=RetrieveDebugVector(requested_k=5, returned_k=0, min=0, max=0, top_scores=[]),
            merge=RetrieveDebugMerge(weights={"vector": 0.6, "bm25": 0.4}, deduped_count=0, final_k=0),
        ),
    )
    resp = client.post(
        "/answer",
        json={"query": "test"},
        headers={"Authorization": "Bearer tenant:contract_test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == ANSWER_RESPONSE_FIELDS, f"answer has extra keys: {set(data) - ANSWER_RESPONSE_FIELDS}"
    assert "citations" in data
    assert isinstance(data["citations"], dict)
    assert "debug" in data
    for claim in data["claims"]:
        assert set(claim) == CLAIM_FIELDS, f"claim has extra keys: {set(claim) - CLAIM_FIELDS}"


@patch("apps.api.services.answer.retrieve_ac")
def test_answer_response_shape_with_claims(mock_retrieve) -> None:
    """/answer with evidence returns claims with only text, evidence_ids, confidence."""
    mock_retrieve.return_value = RetrieveResponse(
        candidates=[
            RetrieveCandidate(
                section_id="sec_1",
                merged_score=0.9,
                url="https://example.com",
                version_hash="vh1",
                snippet="Test content.",
            )
        ],
        debug=RetrieveDebug(
            tenant_id="x",
            vector=RetrieveDebugVector(requested_k=5, returned_k=1, min=0.5, max=0.9, top_scores=[0.9]),
            bm25=RetrieveDebugVector(requested_k=5, returned_k=0, min=0, max=0, top_scores=[]),
            merge=RetrieveDebugMerge(weights={"vector": 0.6, "bm25": 0.4}, deduped_count=0, final_k=1),
        ),
    )
    with patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test content.", "version_hash": "vh1"}):
        with patch("apps.api.services.answer.insert_evidence"):
            resp = client.post(
                "/answer",
                json={"query": "test"},
                headers={"Authorization": "Bearer tenant:contract_test"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == ANSWER_RESPONSE_FIELDS
    assert "citations" in data
    assert "debug" in data
    if data["debug"]:
        assert set(data["debug"]) == ANSWER_DEBUG_FIELDS
    assert isinstance(data["citations"], dict)
    for eid, cite in data["citations"].items():
        assert set(cite) == CITATION_FIELDS, f"citation has wrong keys: {set(cite) ^ CITATION_FIELDS}"
    for claim in data["claims"]:
        assert set(claim) == CLAIM_FIELDS


@requires_db
def test_evidence_dict_includes_tenant_id_and_created_at() -> None:
    """Every evidence dict from get_evidence_by_ids includes tenant_id and created_at."""
    from apps.api.services.repo import get_evidence_by_ids, insert_evidence, insert_raw_page, insert_sections
    tenant_id = f"contract_evidence_{uuid.uuid4().hex[:8]}"
    url = "https://example.com/evidence-contract"
    pid = insert_raw_page(tenant_id, url, text="Test content")
    insert_sections(
        tenant_id,
        pid,
        [
            {"section_id": "sec_e1", "text": "Section text", "version_hash": "vh1"},
        ],
    )
    eid = str(uuid.uuid4())
    insert_evidence(
        tenant_id,
        [{"evidence_id": eid, "section_id": "sec_e1", "url": url, "quote_span": "Section", "start_char": 0, "end_char": 7, "version_hash": "vh1"}],
    )
    ev_list = get_evidence_by_ids(tenant_id, [eid])
    assert len(ev_list) >= 1
    for ev in ev_list:
        assert "tenant_id" in ev, "evidence dict must include tenant_id"
        assert "created_at" in ev, "evidence dict must include created_at"
        assert ev["tenant_id"] == tenant_id
        assert ev["created_at"] is None or isinstance(ev["created_at"], str)
