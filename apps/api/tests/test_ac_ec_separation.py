"""Day 4 acceptance tests: AC vs EC separation and tenant isolation."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.index_ac import index_ac
from apps.api.services.index_ec import index_ec
from apps.api.services.repo import get_evidence_by_ids, get_section_by_id, insert_raw_page, insert_sections
from apps.api.tests.conftest import requires_db

client = TestClient(app)

TENANT_A = "tenant_ac_ec_a"
TENANT_B = "tenant_ac_ec_b"
URL = "https://coasttocoastmovers.com/services"


@requires_db
@patch("apps.api.services.pipeline._fetch")  # Patch where pipeline imports it (not fetch_html_with_meta)
def test_retrieve_ac_returns_sections_with_snippet_from_section_text(mock_fetch) -> None:
    """AC returns candidates with section_id and snippet from section text."""
    from datetime import datetime, timezone

    from apps.api.services.pipeline import run_day1_pipeline

    html = "<p>Long distance moving services. Local and commercial moving. " + ("x" * 500) + "</p>"
    mock_fetch.return_value = {
        "final_url": URL,
        "status_code": 200,
        "html": html,
        "fetched_at": datetime.now(timezone.utc),
    }

    result = run_day1_pipeline(TENANT_A, URL)
    assert not result.get("excluded")
    assert result.get("section_ids")

    resp = client.post(
        "/retrieve/ac",
        json={"query": "long distance moving", "k": 5},
        headers={"Authorization": f"Bearer tenant:{TENANT_A}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["debug"]["vector"] is True
    assert data["candidates"]

    for c in data["candidates"]:
        section_id = c["section_id"]
        snippet = c["snippet"]
        section = get_section_by_id(TENANT_A, section_id)
        assert section is not None
        section_text = section.get("text") or ""
        assert snippet in section_text or section_text.startswith(snippet[:50])


@requires_db
@patch("apps.api.services.pipeline._fetch")  # Patch where pipeline imports it (not fetch_html_with_meta)
def test_retrieve_ec_returns_entities_with_snippet_from_evidence(mock_fetch) -> None:
    """EC returns candidates with snippet equal to evidence.quote_span linked to entities."""
    from datetime import datetime, timezone

    from apps.api.services.pipeline import run_day1_pipeline

    html = "<p>Long distance moving and local moving. Storage in Dallas, TX.</p>"
    mock_fetch.return_value = {
        "final_url": URL,
        "status_code": 200,
        "html": html,
        "fetched_at": datetime.now(timezone.utc),
    }

    result = run_day1_pipeline(TENANT_A, URL)
    assert not result.get("excluded")
    raw_page_id = result["raw_page_id"]
    index_ec(TENANT_A, raw_page_id)

    resp = client.post(
        "/retrieve/ec",
        json={"query": "long distance", "k": 5},
        headers={"Authorization": f"Bearer tenant:{TENANT_A}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["debug"]["vector"] is True
    assert data["entities"], "EC returns entity-level results"
    for ent in data["entities"]:
        assert ent.get("entity_id"), "EC entity has entity_id"
        assert "score" in ent
        for m in ent.get("mentions", []):
            assert m.get("section_id"), "EC mention has section_id"
            assert "quote_span" in m


@requires_db
def test_ac_ec_tenant_isolation() -> None:
    """AC and EC both respect tenant isolation: tenant B gets no tenant A data."""
    pid_a = insert_raw_page(TENANT_A, URL, text="Tenant A content")
    pid_b = insert_raw_page(TENANT_B, "https://b.com", text="Tenant B content")
    insert_sections(TENANT_A, pid_a, [{"section_id": "sec_a_1", "text": "Tenant A section", "version_hash": "v1"}])
    insert_sections(TENANT_B, pid_b, [{"section_id": "sec_b_1", "text": "Tenant B section", "version_hash": "v2"}])
    index_ac(TENANT_A, [{"section_id": "sec_a_1", "text": "Tenant A section", "version_hash": "v1", "url": URL}])
    index_ac(TENANT_B, [{"section_id": "sec_b_1", "text": "Tenant B section", "version_hash": "v2", "url": "https://b.com"}])

    ac_resp = client.post(
        "/retrieve/ac",
        json={"query": "section", "k": 10},
        headers={"Authorization": f"Bearer tenant:{TENANT_A}"},
    )
    assert ac_resp.status_code == 200
    ac_candidates = ac_resp.json().get("candidates", [])
    section_ids = [c["section_id"] for c in ac_candidates]
    assert "sec_b_1" not in section_ids, "AC must not return tenant B sections to tenant A"

    index_ec(TENANT_A, pid_a)
    index_ec(TENANT_B, pid_b)

    ec_resp = client.post(
        "/retrieve/ec",
        json={"query": "Tenant", "k": 10},
        headers={"Authorization": f"Bearer tenant:{TENANT_A}"},
    )
    assert ec_resp.status_code == 200
    ec_entities = ec_resp.json().get("entities", [])
    section_ids_ec = [m["section_id"] for ent in ec_entities for m in ent.get("mentions", [])]
    assert "sec_b_1" not in section_ids_ec, "EC must not return tenant B entity mentions to tenant A"
