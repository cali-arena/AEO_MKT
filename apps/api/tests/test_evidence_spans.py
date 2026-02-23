"""Day 3 acceptance tests: evidence spans match section text exactly."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.tests.conftest import requires_db

client = TestClient(app)


@requires_db
@patch("apps.api.services.pipeline._fetch")  # Patch where pipeline imports it (not fetch_html_with_meta)
def test_evidence_quote_span_matches_section_text(mock_fetch) -> None:
    """Run pipeline + /answer; assert evidence.quote_span == section.text[start_char:end_char]."""
    from datetime import datetime, timezone

    from apps.api.services.pipeline import run_day1_pipeline
    from apps.api.services.repo import get_evidence_by_ids, get_section_by_id

    tenant_id = "tenant_evidence_spans"
    url = "https://coasttocoastmovers.com/doc"
    html = "<p>Moving services and storage. Long distance relocation. " + ("content " * 200) + "</p>"
    mock_fetch.return_value = {
        "final_url": url,
        "status_code": 200,
        "html": html,
        "fetched_at": datetime.now(timezone.utc),
    }

    result = run_day1_pipeline(tenant_id, url)
    assert "excluded" not in result or not result.get("excluded")
    assert result.get("section_ids")

    resp = client.post(
        "/answer",
        json={"query": "moving services storage relocation"},
        headers={"Authorization": f"Bearer tenant:{tenant_id}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is False
    assert data["claims"]

    for claim in data["claims"]:
        evidence_ids = claim.get("evidence_ids", [])
        assert evidence_ids, "each claim must have evidence_ids"

        ev_list = get_evidence_by_ids(tenant_id, evidence_ids)
        assert len(ev_list) == len(evidence_ids)

        for ev in ev_list:
            section = get_section_by_id(tenant_id, ev["section_id"])
            assert section is not None
            section_text = section.get("text") or ""
            start = ev.get("start_char")
            end = ev.get("end_char")
            assert start is not None and end is not None
            assert ev["quote_span"] == section_text[start:end]
            assert ev["version_hash"] == section.get("version_hash")
