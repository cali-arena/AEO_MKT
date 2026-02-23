"""Tests for hybrid AC retrieval: BM25 + vector merge, merged_score, debug.

Uses deterministic embedding provider (ENV=test in conftest) - no network.
"""

import os

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

# Ensure deterministic embeddings (no network)
os.environ.setdefault("ENV", "test")
from apps.api.services.index_ac import index_ac
from apps.api.services.repo import insert_raw_page, insert_sections
from apps.api.tests.conftest import requires_db

client = TestClient(app)

TENANT = "tenant_hybrid"


@pytest.fixture
def sections_with_lexical_and_semantic():
    """Sections where lexical match (exact keyword) and semantic match both surface."""
    url = "https://example.com/hybrid"
    pid = insert_raw_page(TENANT, url, text="Main")
    # Exact keyword for BM25; overlapping meaning for vector
    insert_sections(TENANT, pid, [
        {"section_id": "sec_lex", "text": "relocation services and long distance moving packages", "version_hash": "v1"},
        {"section_id": "sec_sem", "text": "We help you move across the country with full-service transport.", "version_hash": "v2"},
    ])
    index_ac(TENANT, [
        {"section_id": "sec_lex", "text": "relocation services and long distance moving packages", "version_hash": "v1", "url": url},
        {"section_id": "sec_sem", "text": "We help you move across the country with full-service transport.", "version_hash": "v2", "url": url},
    ])
    yield TENANT


@pytest.fixture
def sections_bm25_only(_ensure_text_tsv):
    """Sections with text but no ac_embeddings. BM25 finds them; vector returns 0."""
    tenant = "tenant_hybrid_bm25_only"
    url = "https://example.com/bm25-only"
    pid = insert_raw_page(tenant, url, text="Main")
    insert_sections(tenant, pid, [
        {"section_id": "sec_bm25_1", "text": "relocation services and long distance moving", "version_hash": "v1"},
    ])
    # Do NOT call index_ac - no vector embeddings
    yield tenant


@requires_db
def test_hybrid_returns_merged_score_and_both_channels(sections_with_lexical_and_semantic):
    """Query with exact keyword: response has merged_score, debug.vector and debug.bm25 non-empty when applicable."""
    resp = client.post(
        "/retrieve/ac",
        json={"query": "relocation moving", "k": 10},
        headers={"Authorization": f"Bearer tenant:{TENANT}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "candidates" in data
    assert "debug" in data
    debug = data["debug"]
    assert "vector" in debug
    assert "bm25" in debug
    assert "merge" in debug
    assert debug["merge"]["weights"]["vector"] == 0.6
    assert debug["merge"]["weights"]["bm25"] == 0.4

    for c in data["candidates"]:
        assert "merged_score" in c
        assert "vector_score" in c
        assert "bm25_score" in c

    assert debug["vector"]["returned_k"] >= 1, "vector channel should return results"
    assert debug["bm25"]["returned_k"] >= 1, "lexical query should yield BM25 hits"
    assert debug["merge"]["final_k"] == len(data["candidates"])


@requires_db
def test_bm25_empty_vector_finds_something_still_returns_results(sections_with_lexical_and_semantic):
    """When BM25 finds nothing (obscure query) but vector finds something, merged still returns results with bm25_score=0."""
    # Query with words that do not appear in sections: no lexical match; vector still returns top-k by distance
    resp = client.post(
        "/retrieve/ac",
        json={"query": "qwxzy plugh frobnicate", "k": 10},
        headers={"Authorization": f"Bearer tenant:{TENANT}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "candidates" in data
    assert "debug" in data
    debug = data["debug"]
    assert debug["bm25"]["returned_k"] == 0, "obscure query should yield no BM25 hits"
    assert debug["vector"]["returned_k"] >= 1, "vector should still return top-k"
    assert len(data["candidates"]) >= 1, "merged should return results when vector finds something"

    for c in data["candidates"]:
        assert "merged_score" in c
        assert "bm25_score" in c
        assert c["bm25_score"] == 0.0, "BM25 found nothing so all bm25_score must be 0"
        assert c["vector_score"] >= 0


@requires_db
def test_vector_empty_bm25_finds_something_still_returns_results(sections_bm25_only):
    """When vector finds nothing (no ac_embeddings) but BM25 finds matches, merged still returns results with vector_score=0."""
    tenant = sections_bm25_only
    resp = client.post(
        "/retrieve/ac",
        json={"query": "relocation moving", "k": 10},
        headers={"Authorization": f"Bearer tenant:{tenant}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "candidates" in data
    assert "debug" in data
    debug = data["debug"]
    assert debug["vector"]["returned_k"] == 0, "no ac_embeddings so vector should return 0"
    assert debug["bm25"]["returned_k"] >= 1, "lexical query should yield BM25 hits"
    assert len(data["candidates"]) >= 1, "merged should return results when BM25 finds something"

    for c in data["candidates"]:
        assert "merged_score" in c
        assert "vector_score" in c
        assert c["vector_score"] == 0.0, "vector found nothing so all vector_score must be 0"
        assert c["bm25_score"] >= 0
