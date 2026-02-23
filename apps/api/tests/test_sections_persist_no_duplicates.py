"""Test section persistence: run sectionize+persist twice for same raw_page_id => still N sections."""

import uuid
from datetime import datetime, timezone

import pytest

from apps.api.services.ingest import ingest_page
from apps.api.services.normalize import content_hash
from apps.api.services.repo import get_sections_by_raw_page_id
from apps.api.services.sectionize import sectionize_and_persist
from apps.api.tests.conftest import requires_db


@requires_db
def test_sectionize_persist_twice_no_duplicates() -> None:
    """Run sectionize+persistence twice for same raw_page_id -> still N sections only."""
    tenant_id = f"tenant_sections_{uuid.uuid4().hex[:8]}"
    url = "https://example.com/doc"
    html = "<html><body><h1>Title</h1><p>Paragraph one.</p><p>Paragraph two.</p></body></html>"
    text = "Title Paragraph one. Paragraph two."
    fetch = {
        "final_url": url,
        "status_code": 200,
        "html": html,
        "fetched_at": datetime.now(timezone.utc),
    }

    ingest_result = ingest_page(tenant_id, url, fetch)
    raw_page_id = ingest_result["raw_page_id"]
    ch = content_hash(text)
    domain, page_type, policy_ver = "example.com", "unknown", "abc123"

    sectionize_and_persist(
        tenant_id,
        raw_page_id,
        url,
        text,
        html=html,
        raw_page_content_hash=ch,
        domain=domain,
        page_type=page_type,
        crawl_policy_version=policy_ver,
    )
    sections_1 = get_sections_by_raw_page_id(tenant_id, raw_page_id)
    n = len(sections_1)
    assert n >= 1

    sectionize_and_persist(
        tenant_id,
        raw_page_id,
        url,
        text,
        html=html,
        raw_page_content_hash=ch,
        domain=domain,
        page_type=page_type,
        crawl_policy_version=policy_ver,
    )
    sections_2 = get_sections_by_raw_page_id(tenant_id, raw_page_id)
    assert len(sections_2) == n
    assert sections_2[0]["section_id"] == sections_1[0]["section_id"]
