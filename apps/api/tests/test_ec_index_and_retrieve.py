"""Tests for EC indexing and retrieval: build_ec + /retrieve/ec with tenant isolation."""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.index_ec import build_ec
from apps.api.services.repo import insert_raw_page, insert_sections
from apps.api.tests.conftest import requires_db

client = TestClient(app)

TENANT_A = "tenant_ec_a"
TENANT_B = "tenant_ec_b"
ENTITY_PHRASE = "Acme Logistics LLC"
QUERY = "Acme Logistics"


def _mock_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic mock: no network."""
    return [[0.0] * 384 for _ in texts]


@pytest.fixture
def tenant_a_sections():
    """Tenant A with sections containing unique entity phrase 'Acme Logistics LLC'."""
    url = "https://example.com/acme"
    pid = insert_raw_page(TENANT_A, url, text="Main content")
    insert_sections(TENANT_A, pid, [
        {"section_id": "sec_acme_1", "text": f"We partner with {ENTITY_PHRASE} for nationwide shipping.", "version_hash": "vh1"},
        {"section_id": "sec_acme_2", "text": f"Contact {ENTITY_PHRASE} at support@acme.example.", "version_hash": "vh2"},
    ])
    yield TENANT_A


@requires_db
def test_ec_index_and_retrieve_returns_entity_with_mentions(tenant_a_sections):
    """Insert sections with 'Acme Logistics LLC', build EC, retrieve as tenant A => entity with mentions."""
    build_ec(TENANT_A, embed_fn=_mock_embed)

    resp = client.post(
        "/retrieve/ec",
        json={"query": QUERY, "k": 10, "n": 5},
        headers={"Authorization": f"Bearer tenant:{TENANT_A}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["entities"], "tenant A should get entity results"
    ent = next((e for e in data["entities"] if ENTITY_PHRASE in (e.get("canonical_name") or "")), None)
    assert ent is not None, f"expected entity matching '{ENTITY_PHRASE}'"
    assert ent["mentions"], "entity should have at least one mention"
    mention = ent["mentions"][0]
    assert mention["section_id"] in ("sec_acme_1", "sec_acme_2")
    assert ENTITY_PHRASE in mention["quote_span"] or mention["quote_span"] in ENTITY_PHRASE


@requires_db
def test_ec_tenant_isolation_returns_zero_for_tenant_b(tenant_a_sections):
    """Same data indexed for tenant A; tenant B gets 0 results for same query."""
    build_ec(TENANT_A, embed_fn=_mock_embed)

    resp = client.post(
        "/retrieve/ec",
        json={"query": QUERY, "k": 10},
        headers={"Authorization": f"Bearer tenant:{TENANT_B}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["entities"]) == 0, "tenant B must not see tenant A entity data"
