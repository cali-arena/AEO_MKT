"""Day 2 acceptance tests: tenant isolation, no data leakage."""

import pytest

from apps.api.services.grounding import create_evidence_for_sections
from apps.api.services.index_ac import index_ac
from apps.api.services.repo import (
    get_evidence_by_ids,
    get_sections_by_query,
    get_sections_by_raw_page_id,
    insert_raw_page,
    insert_sections,
)
from apps.api.services.retrieve import retrieve_ac
from apps.api.tests.conftest import requires_db

TENANT_A = "tenant_leak_a"
TENANT_B = "tenant_leak_b"
SECTION_A_ID = "sec_leak_a_1"
SECTION_B_ID = "sec_leak_b_1"
URL_A = "https://a.example.com"
URL_B = "https://b.example.com"
# Distinctive content so query matching B strongly returns only B when queried as B
TEXT_A = "Tenant A exclusive moving services and pricing."
TEXT_B = "Tenant B exclusive storage and long-distance relocation."


@pytest.fixture
def seeded_data():
    """Insert one raw_page, one section, one embedding, one evidence per tenant."""
    pid_a = insert_raw_page(TENANT_A, URL_A, text="Content A")
    pid_b = insert_raw_page(TENANT_B, URL_B, text="Content B")
    insert_sections(
        TENANT_A,
        pid_a,
        [{"section_id": SECTION_A_ID, "text": TEXT_A, "version_hash": "vha"}],
    )
    insert_sections(
        TENANT_B,
        pid_b,
        [{"section_id": SECTION_B_ID, "text": TEXT_B, "version_hash": "vhb"}],
    )
    yield {"pid_a": pid_a, "pid_b": pid_b}


@pytest.fixture
def seeded_and_indexed_data(seeded_data):
    """Seeded data plus AC embeddings and evidence indexed for both tenants."""
    pid_a = seeded_data["pid_a"]
    pid_b = seeded_data["pid_b"]
    sections_a = get_sections_by_raw_page_id(TENANT_A, pid_a)
    sections_b = get_sections_by_raw_page_id(TENANT_B, pid_b)
    ac_a = [{"section_id": s["section_id"], "text": s["text"], "version_hash": s["version_hash"], "url": URL_A} for s in sections_a]
    ac_b = [{"section_id": s["section_id"], "text": s["text"], "version_hash": s["version_hash"], "url": URL_B} for s in sections_b]
    if ac_a:
        index_ac(TENANT_A, ac_a)
    if ac_b:
        index_ac(TENANT_B, ac_b)
    create_evidence_for_sections(TENANT_A, sections_a, URL_A)
    create_evidence_for_sections(TENANT_B, sections_b, URL_B)
    yield


def _get_evidence_ids_for_section(tenant_id: str, section_id: str) -> list[str]:
    from apps.api.services.repo import get_evidence_ids_by_section_ids

    m = get_evidence_ids_by_section_ids(tenant_id, [section_id])
    return m.get(section_id, [])


@requires_db
def test_tenant_a_gets_only_own_sections(seeded_data) -> None:
    """Call retrieval as tenant A. Assert zero candidates from tenant B."""
    results = get_sections_by_query(TENANT_A, "content", k=20)
    section_ids = [r["section_id"] for r in results]
    assert SECTION_B_ID not in section_ids, "tenant A must not receive tenant B data"
    assert SECTION_A_ID in section_ids


@requires_db
def test_tenant_b_gets_only_own_sections(seeded_data) -> None:
    """Call retrieval as tenant B. Assert zero candidates from tenant A."""
    results = get_sections_by_query(TENANT_B, "content", k=20)
    section_ids = [r["section_id"] for r in results]
    assert SECTION_A_ID not in section_ids, "tenant B must not receive tenant A data"
    assert SECTION_B_ID in section_ids


@requires_db
def test_retrieve_ac_tenant_a_no_b_leakage(seeded_and_indexed_data) -> None:
    """Vector retrieval as tenant A must never return tenant B sections."""
    resp = retrieve_ac(TENANT_A, "content", k=20)
    section_ids = [c.section_id for c in resp.candidates]
    assert SECTION_B_ID not in section_ids, "tenant A must not receive tenant B data from vector retrieval"


@requires_db
def test_retrieve_ac_tenant_b_no_a_leakage(seeded_and_indexed_data) -> None:
    """Vector retrieval as tenant B must never return tenant A sections."""
    resp = retrieve_ac(TENANT_B, "content", k=20)
    section_ids = [c.section_id for c in resp.candidates]
    assert SECTION_A_ID not in section_ids, "tenant B must not receive tenant A data from vector retrieval"


@requires_db
def test_retrieve_ac_query_matching_b_as_a_returns_only_a_or_zero(seeded_and_indexed_data) -> None:
    """Query as tenant A with query that strongly matches tenant B content. Candidates must be only tenant A or zero."""
    # Query matches B's distinctive text; retrieval filters by tenant_id so A should get 0 (A has different content)
    resp = retrieve_ac(TENANT_A, "Tenant B exclusive storage and long-distance relocation", k=20)
    section_ids = [c.section_id for c in resp.candidates]
    urls = [c.url for c in resp.candidates]
    assert SECTION_B_ID not in section_ids, "must not leak tenant B sections to tenant A"
    assert all(sid == SECTION_A_ID for sid in section_ids), "all section_ids must be tenant A or empty"
    assert all(u == URL_A or not u for u in urls), "all URLs must be tenant A or empty"


@requires_db
def test_evidence_lookup_tenant_mismatch_returns_empty(seeded_and_indexed_data) -> None:
    """Fetching evidence_ids with tenant mismatch returns empty."""
    evidence_ids_b = _get_evidence_ids_for_section(TENANT_B, SECTION_B_ID)
    assert len(evidence_ids_b) >= 1, "tenant B should have evidence"

    ev = get_evidence_by_ids(TENANT_A, evidence_ids_b)
    assert ev == [], "tenant A must not receive tenant B evidence"
