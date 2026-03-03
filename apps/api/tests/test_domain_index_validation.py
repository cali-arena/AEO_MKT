"""DB validation: per-domain counts and debug index-stats. No global-count logic."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.domain_index_validation import (
    count_ac_embeddings,
    count_raw_pages,
    count_sections,
)
from apps.api.services.pipeline import run_day1_pipeline
from apps.api.tests.conftest import requires_db

client = TestClient(app)

TENANT_ID = "tenant_domain_validation"
DOMAIN_INGESTED = "coasttocoastmovers.com"
DOMAIN_OTHER = "other.example.com"


@requires_db
@patch("apps.api.services.pipeline._fetch")
def test_domain_index_counts_after_ingest_and_domain_scoped(mock_fetch) -> None:
    """
    Run ingest for one domain; assert sections and ac_embeddings > 0.
    Assert counts are domain-scoped: another domain returns 0 (no global counts).
    """
    from datetime import datetime, timezone

    url = f"https://{DOMAIN_INGESTED}/page"
    html = "<p>Moving services and storage. Long distance relocation. " + ("content " * 80) + "</p>"
    mock_fetch.return_value = {
        "final_url": url,
        "status_code": 200,
        "html": html,
        "fetched_at": datetime.now(timezone.utc),
    }

    result = run_day1_pipeline(TENANT_ID, url)
    assert result.get("excluded") is not True, "page should not be excluded"
    assert result.get("section_ids"), "pipeline should create sections"

    # Per-domain counts for ingested domain must be > 0
    n_raw = count_raw_pages(TENANT_ID, DOMAIN_INGESTED)
    n_sec = count_sections(TENANT_ID, DOMAIN_INGESTED)
    n_ac = count_ac_embeddings(TENANT_ID, DOMAIN_INGESTED)
    assert n_raw > 0, "raw_pages for ingested domain must be > 0"
    assert n_sec > 0, "sections for ingested domain must be > 0"
    assert n_ac > 0, "ac_embeddings for ingested domain must be > 0"

    # Other domain must have 0 counts (domain-scoped; no global counts)
    assert count_raw_pages(TENANT_ID, DOMAIN_OTHER) == 0
    assert count_sections(TENANT_ID, DOMAIN_OTHER) == 0
    assert count_ac_embeddings(TENANT_ID, DOMAIN_OTHER) == 0


@requires_db
@patch("apps.api.services.pipeline._fetch")
def test_debug_index_stats_endpoint_returns_domain_scoped_counts(mock_fetch) -> None:
    """
    Ingest one domain, then GET /tenants/{tenant_id}/domains/{domain}/debug/index-stats.
    Assert response has raw_pages, sections, ac_embeddings, ec_embeddings, index_state;
    ingested domain has counts > 0; other domain has 0.
    """
    from datetime import datetime, timezone

    url = f"https://{DOMAIN_INGESTED}/stats"
    html = "<p>Debug stats test. Content here. " + ("x " * 100) + "</p>"
    mock_fetch.return_value = {
        "final_url": url,
        "status_code": 200,
        "html": html,
        "fetched_at": datetime.now(timezone.utc),
    }
    run_day1_pipeline(TENANT_ID, url)

    # Ingested domain: debug endpoint returns counts and index_state
    resp = client.get(
        f"/tenants/{TENANT_ID}/domains/{DOMAIN_INGESTED}/debug/index-stats",
        headers={"Authorization": f"Bearer tenant:{TENANT_ID}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "raw_pages" in data
    assert "sections" in data
    assert "ac_embeddings" in data
    assert "ec_embeddings" in data
    assert "index_state" in data
    assert data["raw_pages"] > 0
    assert data["sections"] > 0
    assert data["ac_embeddings"] > 0

    # Other domain: all counts 0
    resp_other = client.get(
        f"/tenants/{TENANT_ID}/domains/{DOMAIN_OTHER}/debug/index-stats",
        headers={"Authorization": f"Bearer tenant:{TENANT_ID}"},
    )
    assert resp_other.status_code == 200
    other = resp_other.json()
    assert other["raw_pages"] == 0
    assert other["sections"] == 0
    assert other["ac_embeddings"] == 0
    assert other["ec_embeddings"] == 0
