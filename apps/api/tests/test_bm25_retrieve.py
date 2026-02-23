"""Tests for BM25 FTS retrieval: bm25_retrieve_sections."""

import pytest
from sqlalchemy import text

from apps.api.services.bm25 import bm25_retrieve_sections
from apps.api.services.repo import insert_raw_page, insert_sections
from apps.api.tests.conftest import requires_db


@pytest.fixture
def tenant_with_sections():
    tenant_id = "tenant_bm25_test"
    url = "https://example.com/bm25"
    pid = insert_raw_page(tenant_id, url, text="Main")
    insert_sections(tenant_id, pid, [
        {"section_id": "sec_1", "text": "long distance moving and relocation services", "version_hash": "v1"},
        {"section_id": "sec_2", "text": "local moving and storage options", "version_hash": "v2"},
        {"section_id": "sec_3", "text": "commercial relocation nationwide", "version_hash": "v3"},
    ])
    yield tenant_id


@requires_db
def test_bm25_retrieve_sections_returns_section_id_and_score(tenant_with_sections):
    """bm25_retrieve_sections returns list of {section_id, bm25_score} with tenant filter."""
    tenant_id = tenant_with_sections
    results = bm25_retrieve_sections(tenant_id, "relocation moving", k=5)

    assert isinstance(results, list)
    assert len(results) >= 1
    for r in results:
        assert "section_id" in r
        assert "bm25_score" in r
        assert isinstance(r["section_id"], str)
        assert isinstance(r["bm25_score"], (int, float))
        assert r["bm25_score"] >= 0


@requires_db
def test_bm25_retrieve_sections_deterministic_ordering(tenant_with_sections):
    """Results are ordered by bm25_score DESC, then section_id ASC for ties."""
    tenant_id = tenant_with_sections
    results = bm25_retrieve_sections(tenant_id, "moving", k=10)

    scores = [r["bm25_score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    # Secondary sort by section_id (deterministic)
    for i in range(len(results) - 1):
        if results[i]["bm25_score"] == results[i + 1]["bm25_score"]:
            assert results[i]["section_id"] <= results[i + 1]["section_id"]


@requires_db
def test_bm25_retrieve_sections_tenant_isolation(tenant_with_sections):
    """Different tenant gets no results from another tenant's sections."""
    tenant_id = tenant_with_sections
    other_tenant = "other_tenant_xyz"
    results = bm25_retrieve_sections(other_tenant, "relocation moving", k=5)

    assert results == []


@requires_db
def test_bm25_retrieve_sections_empty_query_returns_empty(tenant_with_sections):
    """Empty or whitespace query returns []."""
    tenant_id = tenant_with_sections
    assert bm25_retrieve_sections(tenant_id, "", k=5) == []
    assert bm25_retrieve_sections(tenant_id, "   ", k=5) == []
