"""Tests for section_hash, version_hash, and Day 3 versioning acceptance."""

from unittest.mock import patch

import pytest

from apps.api.utils.hashing import section_hash, version_hash

from apps.api.tests.conftest import requires_db


def test_section_hash_same_text_same_hash() -> None:
    """Same text produces same section_hash."""
    text = "Hello world"
    assert section_hash(text) == section_hash(text)


def test_section_hash_different_text_different_hash() -> None:
    """Changed text produces different section_hash."""
    assert section_hash("foo") != section_hash("bar")


def test_version_hash_same_input_same_hash() -> None:
    """Same text and extra produces same version_hash."""
    assert version_hash("x", "y") == version_hash("x", "y")


def test_version_hash_changed_text_different_hash() -> None:
    """Changed text produces different version_hash."""
    assert version_hash("a") != version_hash("b")


def test_version_hash_changed_extra_different_hash() -> None:
    """Changed extra produces different version_hash."""
    assert version_hash("x", "a") != version_hash("x", "b")


def test_version_hash_empty_extra() -> None:
    """Empty extra yields deterministic hash."""
    h1 = version_hash("t")
    h2 = version_hash("t", "")
    assert h1 == h2


def test_hashes_are_hex_strings() -> None:
    """Hashes are 64-char hex strings."""
    h = section_hash("x")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


@requires_db
@patch("apps.api.services.pipeline._fetch")  # Patch where pipeline imports it (not fetch_html_with_meta)
def test_day3_versioning_section_id_stable_version_hash_changes_raw_page_version_increments(
    mock_fetch,
) -> None:
    """Day 3: section_id stable across content change; version_hash changes; raw_page.version increments."""
    from apps.api.services.pipeline import run_day1_pipeline
    from apps.api.services.repo import get_latest_raw_page_by_canonical_url, get_sections_by_raw_page_id

    tenant_id = "tenant_versioning_" + __import__("uuid").uuid4().hex[:8]
    url = "https://coasttocoastmovers.com/doc"
    # 2+ headings => heading-based extraction. First section identical => section_id stable; footer differs => content_hash changes, version increments
    html1 = "<h1>Doc Title</h1><p>Same intro paragraph for first section.</p><h2>Footer</h2><p>Footer run 1.</p>"
    html2 = "<h1>Doc Title</h1><p>Same intro paragraph for first section.</p><h2>Footer</h2><p>Footer run 2 changed.</p>"

    from datetime import datetime, timezone

    responses = [
        {"final_url": url, "status_code": 200, "html": html1, "fetched_at": datetime.now(timezone.utc)},
        {"final_url": url, "status_code": 200, "html": html2, "fetched_at": datetime.now(timezone.utc)},
    ]
    mock_fetch.side_effect = iter(responses)

    result1 = run_day1_pipeline(tenant_id, url)
    assert "excluded" not in result1 or not result1.get("excluded")
    assert result1.get("section_ids")
    sections1 = get_sections_by_raw_page_id(tenant_id, result1["raw_page_id"])
    assert len(sections1) >= 1
    chunk0_section_id = sections1[0]["section_id"]
    chunk0_version_hash = sections1[0]["version_hash"]
    latest1 = get_latest_raw_page_by_canonical_url(tenant_id, url)
    assert latest1["version"] == 1

    result2 = run_day1_pipeline(tenant_id, url)
    assert "excluded" not in result2 or not result2.get("excluded")
    sections2 = get_sections_by_raw_page_id(tenant_id, result2["raw_page_id"])
    assert len(sections2) >= 1
    assert sections2[0]["section_id"] == chunk0_section_id
    assert sections2[0]["version_hash"] != chunk0_version_hash
    latest2 = get_latest_raw_page_by_canonical_url(tenant_id, url)
    assert latest2["version"] == 2
