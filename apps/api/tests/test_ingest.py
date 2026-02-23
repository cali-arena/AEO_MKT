"""Unit tests for ingest content change detection."""

import uuid
from datetime import datetime, timezone

import pytest

from apps.api.services.ingest import ingest_page
from apps.api.services.repo import get_latest_raw_page_by_canonical_url
from apps.api.tests.conftest import requires_db


@requires_db
def test_version_increment_on_content_change() -> None:
    """When content_hash changes, new raw_page has version = previous + 1."""
    tenant_id = f"tenant_ingest_test_{uuid.uuid4().hex[:8]}"
    url = "https://example.com/doc"
    canonical_url = url

    fetch1 = {
        "final_url": canonical_url,
        "status_code": 200,
        "html": "<p>Original content</p>",
        "fetched_at": datetime.now(timezone.utc),
    }
    fetch2 = {
        "final_url": canonical_url,
        "status_code": 200,
        "html": "<p>Updated content</p>",
        "fetched_at": datetime.now(timezone.utc),
    }

    r1 = ingest_page(tenant_id, url, fetch1)
    assert r1["unchanged"] is False
    raw_page_id_1 = r1["raw_page_id"]

    latest = get_latest_raw_page_by_canonical_url(tenant_id, canonical_url)
    assert latest is not None
    assert latest["version"] == 1

    r2 = ingest_page(tenant_id, url, fetch2)
    assert r2["unchanged"] is False
    raw_page_id_2 = r2["raw_page_id"]
    assert raw_page_id_2 != raw_page_id_1

    latest = get_latest_raw_page_by_canonical_url(tenant_id, canonical_url)
    assert latest["version"] == 2
    assert latest["id"] == raw_page_id_2


@requires_db
def test_unchanged_when_content_hash_same() -> None:
    """When content_hash matches existing, return unchanged and do not create new row."""
    tenant_id = f"tenant_ingest_unchanged_{uuid.uuid4().hex[:8]}"
    url = "https://example.com/same"
    fetch = {
        "final_url": url,
        "status_code": 200,
        "html": "<p>Same content</p>",
        "fetched_at": datetime.now(timezone.utc),
    }

    r1 = ingest_page(tenant_id, url, fetch)
    assert r1["unchanged"] is False
    raw_page_id_1 = r1["raw_page_id"]

    r2 = ingest_page(tenant_id, url, fetch)
    assert r2["unchanged"] is True
    assert r2["raw_page_id"] == raw_page_id_1
