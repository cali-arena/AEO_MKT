"""Deterministic tests: /retrieve/ec is vector-only (no ILIKE fallback). Tenant isolation."""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.index_ec import build_ec
from apps.api.services.repo import insert_raw_page, insert_sections
from apps.api.tests.conftest import requires_db

client = TestClient(app)

TENANT_A = "tenant_ec_vector_a"
TENANT_B = "tenant_ec_vector_b"
ENTITY_PHRASE = "Coastal Moving Corp"
QUERY = "Coastal Moving"


def _mock_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic mock: no network."""
    return [[0.0] * 384 for _ in texts]


@pytest.fixture
def tenant_a_indexed():
    """Tenant A with sections containing ENTITY_PHRASE, EC indexed."""
    url = "https://example.com/coastal"
    pid = insert_raw_page(TENANT_A, url, text="Moving services")
    insert_sections(TENANT_A, pid, [
        {"section_id": "sec_1", "text": f"{ENTITY_PHRASE} offers long-distance moves.", "version_hash": "v1"},
    ])
    build_ec(TENANT_A, embed_fn=_mock_embed)
    yield TENANT_A


@requires_db
def test_tenant_a_indexed_query_returns_entity(tenant_a_indexed) -> None:
    """Tenant A indexed => query returns at least one entity (vector-only)."""
    resp = client.post(
        "/retrieve/ec",
        json={"query": QUERY, "k": 10, "n": 5},
        headers={"Authorization": f"Bearer tenant:{TENANT_A}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["debug"]["vector"] is True
    assert data["entities"], "tenant A should get entity results"
    ent = data["entities"][0]
    assert "entity_id" in ent
    assert "canonical_name" in ent
    assert "entity_type" in ent
    assert "score" in ent
    assert "mentions" in ent
    if ent["mentions"]:
        m = ent["mentions"][0]
        assert "section_id" in m
        assert "quote_span" in m
        assert "start_offset" in m
        assert "end_offset" in m


@requires_db
def test_tenant_b_same_query_zero_results(tenant_a_indexed) -> None:
    """Tenant B same query => 0 results (tenant isolation, no cross-tenant data)."""
    resp = client.post(
        "/retrieve/ec",
        json={"query": QUERY, "k": 10},
        headers={"Authorization": f"Bearer tenant:{TENANT_B}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entities"]) == 0, "tenant B must not see tenant A entity data"
