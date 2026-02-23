"""Unit tests for raw_page versioning: same url same text => no new row; same url changed text => version increment."""

import uuid
from datetime import datetime, timezone

import pytest

from apps.api.services.ingest import ingest_page
from apps.api.services.repo import get_latest_raw_page_by_canonical_url
from apps.api.tests.conftest import requires_db


@requires_db
def test_same_url_same_text_no_new_row() -> None:
    """Same url, same text => no new row, changed=False."""
    tenant_id = f"tenant_versioning_same_{uuid.uuid4().hex[:8]}"
    url = "https://example.com/same-content"
    fetch = {
        "final_url": url,
        "status_code": 200,
        "html": "<p>Identical content</p>",
        "fetched_at": datetime.now(timezone.utc),
    }

    r1 = ingest_page(tenant_id, url, fetch)
    assert r1["unchanged"] is False
    assert r1["changed"] is True
    raw_page_id_1 = r1["raw_page_id"]

    r2 = ingest_page(tenant_id, url, fetch)
    assert r2["unchanged"] is True
    assert r2["changed"] is False
    assert r2["raw_page_id"] == raw_page_id_1

    latest = get_latest_raw_page_by_canonical_url(tenant_id, url)
    assert latest is not None
    assert latest["id"] == raw_page_id_1
    assert latest["version"] == 1


@requires_db
def test_same_url_changed_text_new_row_version_increment() -> None:
    """Same url, changed text => new row and version increment."""
    tenant_id = f"tenant_versioning_changed_{uuid.uuid4().hex[:8]}"
    url = "https://example.com/evolving"
    fetch1 = {
        "final_url": url,
        "status_code": 200,
        "html": "<p>Original content</p>",
        "fetched_at": datetime.now(timezone.utc),
    }
    fetch2 = {
        "final_url": url,
        "status_code": 200,
        "html": "<p>Updated content</p>",
        "fetched_at": datetime.now(timezone.utc),
    }

    r1 = ingest_page(tenant_id, url, fetch1)
    assert r1["unchanged"] is False
    assert r1["changed"] is True
    raw_page_id_1 = r1["raw_page_id"]

    latest1 = get_latest_raw_page_by_canonical_url(tenant_id, url)
    assert latest1["version"] == 1
    assert latest1["id"] == raw_page_id_1

    r2 = ingest_page(tenant_id, url, fetch2)
    assert r2["unchanged"] is False
    assert r2["changed"] is True
    raw_page_id_2 = r2["raw_page_id"]
    assert raw_page_id_2 != raw_page_id_1

    latest2 = get_latest_raw_page_by_canonical_url(tenant_id, url)
    assert latest2["version"] == 2
    assert latest2["id"] == raw_page_id_2
