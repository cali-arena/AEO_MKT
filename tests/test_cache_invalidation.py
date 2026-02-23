"""Tests for /answer cache integration: version-based invalidation and tenant isolation."""

import json
import os

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Ensure test env before imports
os.environ.setdefault("ENV", "test")

from apps.api.main import app
from apps.api.schemas.responses import RetrieveCandidate, RetrieveDebug, RetrieveDebugMerge, RetrieveDebugVector, RetrieveResponse
from apps.api.services.repo import upsert_tenant_index_version
from apps.api.tests.conftest import requires_db

client = TestClient(app)


def _candidates(score: float = 0.9):
    return [
        RetrieveCandidate(
            section_id="sec_1",
            merged_score=score,
            vector_score=0.8,
            bm25_score=0.7,
            rerank_score=score,
            rerank_reasons=[],
            url="https://example.com",
            version_hash="vh1",
            snippet="Test content.",
        )
    ]


def _mock_retrieve(score: float = 0.9):
    return RetrieveResponse(
        candidates=_candidates(score),
        debug=RetrieveDebug(
            tenant_id="x",
            vector=RetrieveDebugVector(requested_k=5, returned_k=1),
            bm25=RetrieveDebugVector(requested_k=5, returned_k=1),
            merge=RetrieveDebugMerge(weights={}, deduped_count=0, final_k=1),
        ),
    )


def _fake_llm_gen(prompt, evidence_items):
    eids = [e["evidence_id"] for e in evidence_items]
    return json.dumps({"answer": "Cached answer.", "claims": [{"text": "Cached.", "evidence_ids": eids, "confidence": 0.9}]})


@requires_db
def test_same_query_second_call_hits_cache() -> None:
    """Create versions v1, call /answer twice; second call returns cached payload (retrieve not called again)."""
    tenant_id = "tenant_cache_hit"
    upsert_tenant_index_version(tenant_id, ac_version_hash="ac_v1", ec_version_hash="ec_v1")

    with patch("apps.api.services.answer.retrieve_ac") as mock_retrieve:
        mock_retrieve.return_value = _mock_retrieve()
        with patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test.", "version_hash": "vh1"}):
            with patch("apps.api.services.answer.insert_evidence"):
                with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
                    mock_llm.return_value = type("M", (), {"generate": lambda s, p, e: _fake_llm_gen(p, e)})()

                    r1 = client.post(
                        "/answer",
                        json={"query": "what is the policy"},
                        headers={"Authorization": f"Bearer tenant:{tenant_id}"},
                    )
                    r2 = client.post(
                        "/answer",
                        json={"query": "what is the policy"},
                        headers={"Authorization": f"Bearer tenant:{tenant_id}"},
                    )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["refused"] is False
    assert r2.json()["refused"] is False
    assert r1.json()["answer"] == r2.json()["answer"]
    # Second call should hit cache: retrieve_ac called only once
    assert mock_retrieve.call_count == 1


@requires_db
def test_ac_version_change_causes_cache_miss() -> None:
    """Update ac_version_hash to v2 (simulate re-ingest); call /answer; assert cache miss and new entry."""
    tenant_id = "tenant_ac_invalidate"
    upsert_tenant_index_version(tenant_id, ac_version_hash="ac_v1", ec_version_hash="ec_v1")

    with patch("apps.api.services.answer.retrieve_ac") as mock_retrieve:
        mock_retrieve.return_value = _mock_retrieve()
        with patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test.", "version_hash": "vh1"}):
            with patch("apps.api.services.answer.insert_evidence"):
                with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
                    mock_llm.return_value = type("M", (), {"generate": lambda s, p, e: _fake_llm_gen(p, e)})()

                    r1 = client.post(
                        "/answer",
                        json={"query": "same query"},
                        headers={"Authorization": f"Bearer tenant:{tenant_id}"},
                    )
                    assert r1.status_code == 200
                    assert mock_retrieve.call_count == 1

    upsert_tenant_index_version(tenant_id, ac_version_hash="ac_v2", ec_version_hash="ec_v1")

    with patch("apps.api.services.answer.retrieve_ac") as mock_retrieve:
        mock_retrieve.return_value = _mock_retrieve()
        with patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test.", "version_hash": "vh1"}):
            with patch("apps.api.services.answer.insert_evidence"):
                with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
                    mock_llm.return_value = type("M", (), {"generate": lambda s, p, e: _fake_llm_gen(p, e)})()

                    r2 = client.post(
                        "/answer",
                        json={"query": "same query"},
                        headers={"Authorization": f"Bearer tenant:{tenant_id}"},
                    )

    assert r2.status_code == 200
    assert mock_retrieve.call_count == 1


@requires_db
def test_tenant_b_never_hits_tenant_a_cache() -> None:
    """Tenant B with same query as Tenant A never gets Tenant A's cached answer."""
    tenant_a = "tenant_a_isolation"
    tenant_b = "tenant_b_isolation"
    query = "isolated query"
    upsert_tenant_index_version(tenant_a, ac_version_hash="ac_v1", ec_version_hash="ec_v1")
    upsert_tenant_index_version(tenant_b, ac_version_hash="ac_v1", ec_version_hash="ec_v1")

    with patch("apps.api.services.answer.retrieve_ac") as mock_retrieve:
        mock_retrieve.return_value = _mock_retrieve()
        with patch("apps.api.services.answer.get_section_by_id", return_value={"text": "Test.", "version_hash": "vh1"}):
            with patch("apps.api.services.answer.insert_evidence"):
                with patch("apps.api.services.answer.get_llm_provider") as mock_llm:
                    mock_llm.return_value = type("M", (), {"generate": lambda s, p, e: _fake_llm_gen(p, e)})()

                    ra1 = client.post(
                        "/answer",
                        json={"query": query},
                        headers={"Authorization": f"Bearer tenant:{tenant_a}"},
                    )
                    rb1 = client.post(
                        "/answer",
                        json={"query": query},
                        headers={"Authorization": f"Bearer tenant:{tenant_b}"},
                    )
                    ra2 = client.post(
                        "/answer",
                        json={"query": query},
                        headers={"Authorization": f"Bearer tenant:{tenant_a}"},
                    )
                    rb2 = client.post(
                        "/answer",
                        json={"query": query},
                        headers={"Authorization": f"Bearer tenant:{tenant_b}"},
                    )

    assert ra1.status_code == 200
    assert rb1.status_code == 200
    assert ra2.status_code == 200
    assert rb2.status_code == 200
    # A1 miss, B1 miss, A2 hit, B2 hit -> retrieve called only twice
    assert mock_retrieve.call_count == 2
    assert ra1.json()["answer"] == ra2.json()["answer"]
    assert rb1.json()["answer"] == rb2.json()["answer"]
