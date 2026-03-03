"""Test that unchanged raw_page still triggers sectionize+embeddings when artifacts are missing."""

from unittest.mock import patch

import pytest

from apps.api.services.pipeline import run_day1_pipeline
from apps.api.services.repo import (
    delete_ac_embeddings_for_section_ids,
    get_artifact_counts_for_raw_page,
    get_sections_by_raw_page_id,
)
from apps.api.tests.conftest import requires_db


@requires_db
@patch("apps.api.services.pipeline._fetch")
def test_unchanged_but_missing_embeddings_rebuilds(mock_fetch) -> None:
    """
    Arrange: run pipeline once so raw_page exists with same content_hash on second run (unchanged).
    Delete ac_embeddings for that raw_page's sections.
    Act: run pipeline again (ingest returns unchanged=True).
    Assert: pipeline repairs: sectionize + index_ac run, indexed_count > 0, sections/embeddings re-created.
    """
    from datetime import datetime, timezone

    tenant_id = "tenant_unchanged_repair"
    url = "https://coasttocoastmovers.com/repair"
    html = "<p>Content for repair test. " + ("x " * 80) + "</p>"
    mock_fetch.return_value = {
        "final_url": url,
        "status_code": 200,
        "html": html,
        "fetched_at": datetime.now(timezone.utc),
    }

    result1 = run_day1_pipeline(tenant_id, url)
    assert result1.get("excluded") is not True
    raw_page_id = result1["raw_page_id"]
    section_ids_1 = result1.get("section_ids") or []
    assert len(section_ids_1) > 0, "first run should create sections"
    assert (result1.get("indexed_count") or 0) > 0, "first run should create ac_embeddings"

    sections_count, ac_count, ec_count = get_artifact_counts_for_raw_page(tenant_id, raw_page_id)
    assert sections_count > 0 and ac_count > 0

    delete_ac_embeddings_for_section_ids(tenant_id, section_ids_1)
    sections_count2, ac_count2, _ = get_artifact_counts_for_raw_page(tenant_id, raw_page_id)
    assert ac_count2 == 0, "ac_embeddings should be deleted"

    result2 = run_day1_pipeline(tenant_id, url)
    assert result2.get("excluded") is not True
    assert result2.get("raw_page_id") == raw_page_id
    assert result2.get("unchanged") is False, "pipeline should report repaired (unchanged=False) so index_ec runs"
    assert len(result2.get("section_ids") or []) > 0
    assert (result2.get("indexed_count") or 0) > 0, "embeddings should be re-created"

    sections_count3, ac_count3, _ = get_artifact_counts_for_raw_page(tenant_id, raw_page_id)
    assert sections_count3 > 0 and ac_count3 > 0, "counts should be restored after repair"


@requires_db
@patch("apps.api.services.pipeline._fetch")
def test_unchanged_but_missing_sections_rebuilds(mock_fetch) -> None:
    """
    Arrange: run pipeline once; then delete sections for that raw_page (simulate missing artifacts).
    Act: run pipeline again (unchanged).
    Assert: sectionize + index_ac run, sections and embeddings re-created.
    """
    from datetime import datetime, timezone

    from apps.api.services.repo import delete_sections_for_raw_page

    tenant_id = "tenant_unchanged_repair_sections"
    url = "https://coasttocoastmovers.com/repair2"
    html = "<p>Content for sections repair. " + ("y " * 80) + "</p>"
    mock_fetch.return_value = {
        "final_url": url,
        "status_code": 200,
        "html": html,
        "fetched_at": datetime.now(timezone.utc),
    }

    result1 = run_day1_pipeline(tenant_id, url)
    assert result1.get("excluded") is not True
    raw_page_id = result1["raw_page_id"]
    assert len(result1.get("section_ids") or []) > 0

    deleted = delete_sections_for_raw_page(tenant_id, raw_page_id)
    assert deleted > 0
    sections_count, ac_count, _ = get_artifact_counts_for_raw_page(tenant_id, raw_page_id)
    assert sections_count == 0

    result2 = run_day1_pipeline(tenant_id, url)
    assert result2.get("excluded") is not True
    assert result2.get("unchanged") is False
    assert len(result2.get("section_ids") or []) > 0
    assert (result2.get("indexed_count") or 0) > 0

    sections_list = get_sections_by_raw_page_id(tenant_id, raw_page_id)
    assert len(sections_list) > 0
