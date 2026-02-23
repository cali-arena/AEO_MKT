"""Cross-tenant retrieval leakage tests: proves tenant B gets zero results when querying tenant A content.

Uses TestClient; ENV=test gives deterministic embeddings (no external calls).
"""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.index_ac import index_ac
from apps.api.services.repo import get_sections_by_raw_page_id, insert_raw_page, insert_sections
from apps.api.tests.conftest import requires_db

# Tenants and unique content
TENANT_A = "tenant_leakage_a"
TENANT_B = "tenant_leakage_b"
URL_A = "https://a.example.com/doc"
URL_B = "https://b.example.com/doc"
ALPHA_PHRASE = "alpha_only_phrase_9f3k"
SECTION_A_ID = "sec_leak_a_1"
SECTION_B_ID = "sec_leak_b_1"

client = TestClient(app)


@pytest.fixture
def tenant_a_data():
    """Insert raw_page + section for tenant_a containing unique phrase."""
    pid = insert_raw_page(TENANT_A, URL_A, text=f"Content with {ALPHA_PHRASE} for tenant A only.")
    insert_sections(
        TENANT_A,
        pid,
        [{"section_id": SECTION_A_ID, "text": f"This section has {ALPHA_PHRASE} exclusively.", "version_hash": "vha"}],
    )
    yield {"pid": pid}


@pytest.fixture
def tenant_b_data():
    """Insert raw_page + section for tenant_b with unrelated content."""
    pid = insert_raw_page(TENANT_B, URL_B, text="Unrelated content for tenant B.")
    insert_sections(
        TENANT_B,
        pid,
        [{"section_id": SECTION_B_ID, "text": "Storage and logistics overview.", "version_hash": "vhb"}],
    )
    yield {"pid": pid}


@pytest.fixture
def indexed_both_tenants(tenant_a_data, tenant_b_data):
    """Both tenants have AC embeddings indexed. Deterministic (ENV=test)."""
    pid_a = tenant_a_data["pid"]
    pid_b = tenant_b_data["pid"]
    sections_a = get_sections_by_raw_page_id(TENANT_A, pid_a)
    sections_b = get_sections_by_raw_page_id(TENANT_B, pid_b)
    ac_a = [{"section_id": s["section_id"], "text": s["text"], "version_hash": s["version_hash"], "url": URL_A} for s in sections_a]
    ac_b = [{"section_id": s["section_id"], "text": s["text"], "version_hash": s["version_hash"], "url": URL_B} for s in sections_b]
    if ac_a:
        index_ac(TENANT_A, ac_a)
    if ac_b:
        index_ac(TENANT_B, ac_b)
    yield


@requires_db
def test_cross_tenant_retrieval_returns_zero_results(indexed_both_tenants) -> None:
    """Tenant B querying tenant A's unique phrase returns zero results (no cross-tenant leakage)."""
    resp = client.post(
        "/retrieve/ac",
        json={"query": ALPHA_PHRASE, "k": 20},
        headers={"Authorization": f"Bearer tenant:{TENANT_B}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    candidates = data.get("candidates", [])
    assert len(candidates) == 0, "Tenant B must not receive tenant A content"

    debug = data.get("debug", {})
    assert debug.get("candidate_count", 0) == 0
    assert debug.get("post_filter_count", 0) == 0
    assert debug.get("tenant_id") == TENANT_B
