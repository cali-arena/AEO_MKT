"""Tests for build_ec: tenant-scoped EC build from sections."""

import pytest

from apps.api.services.index_ec import build_ec
from apps.api.tests.conftest import requires_db
from apps.api.services.repo import get_ec_version, get_sections_for_tenant, insert_raw_page, insert_sections


def _mock_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic mock: no network."""
    return [[0.0] * 384 for _ in texts]


@pytest.fixture
def tenant_with_sections():
    tenant_id = "test-build-ec-tenant"
    url = "https://example.com/page"
    pid = insert_raw_page(tenant_id, url, text="Main content")
    insert_sections(tenant_id, pid, [
        {"section_id": "sec_1", "text": "Contact us in Dallas, TX or call +1-555-123-4567.", "version_hash": "vh1"},
        {"section_id": "sec_2", "text": "We serve New York, NY and Austin, TX.", "version_hash": "vh2"},
    ])
    yield tenant_id


@requires_db
def test_build_ec_extracts_entities_and_stores(tenant_with_sections):
    """build_ec loads sections, extracts entities, upserts entities+mentions, embeds, stores version."""
    tenant_id = tenant_with_sections
    result = build_ec(tenant_id, embed_fn=_mock_embed)

    assert result["entities_count"] >= 1
    assert result["mentions_count"] >= 1
    assert result["indexed_ec_count"] >= 1
    assert len(result["ec_version_hash"]) == 16

    version = get_ec_version(tenant_id)
    assert version == result["ec_version_hash"]


@requires_db
def test_build_ec_idempotent_same_version(tenant_with_sections):
    """Re-running build_ec with same sections yields same ec_version_hash."""
    tenant_id = tenant_with_sections
    r1 = build_ec(tenant_id, embed_fn=_mock_embed)
    r2 = build_ec(tenant_id, embed_fn=_mock_embed)

    assert r1["ec_version_hash"] == r2["ec_version_hash"]
    assert r1["entities_count"] == r2["entities_count"]
    assert r1["mentions_count"] == r2["mentions_count"]


@requires_db
def test_build_ec_no_sections_returns_empty():
    """build_ec for tenant with no sections returns zeros and empty hash."""
    result = build_ec("tenant-no-sections", embed_fn=_mock_embed)

    assert result["entities_count"] == 0
    assert result["mentions_count"] == 0
    assert result["indexed_ec_count"] == 0
    assert result["ec_version_hash"] == ""
