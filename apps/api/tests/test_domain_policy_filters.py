"""Test domain and crawl_policy_version inserts and query filters."""

import pytest

from apps.api.services.repo import (
    count_raw_pages_by_crawl_policy_version,
    count_raw_pages_by_domain,
    count_sections_by_crawl_policy_version,
    count_sections_by_domain,
    insert_raw_page,
    insert_sections,
)
from apps.api.tests.conftest import requires_db

TENANT_ID = "test_domain_policy_tenant"
DOMAIN_A = "filter-test-a.com"
DOMAIN_B = "filter-test-b.com"
POLICY_VER_A = "aaaa11112222"
POLICY_VER_B = "bbbb33334444"


@requires_db
def test_domain_and_policy_version_filters() -> None:
    """Insert raw_pages and sections with domain/crawl_policy_version; verify query filters work."""
    # Insert 2 raw_page rows (same tenant) with different domains and policy_version
    pid_a = insert_raw_page(
        TENANT_ID,
        f"https://{DOMAIN_A}/page1",
        canonical_url=f"https://{DOMAIN_A}/page1",
        text="Content A",
        domain=DOMAIN_A,
        page_type="info_static",
        crawl_policy_version=POLICY_VER_A,
    )
    pid_b = insert_raw_page(
        TENANT_ID,
        f"https://{DOMAIN_B}/page2",
        canonical_url=f"https://{DOMAIN_B}/page2",
        text="Content B",
        domain=DOMAIN_B,
        page_type="quote_flow",
        crawl_policy_version=POLICY_VER_B,
    )

    # Insert 2 sections per page
    insert_sections(
        TENANT_ID,
        pid_a,
        [
            {
                "section_id": "sec_a_1",
                "text": "Section A1",
                "version_hash": "v1",
                "domain": DOMAIN_A,
                "page_type": "info_static",
                "crawl_policy_version": POLICY_VER_A,
            },
            {
                "section_id": "sec_a_2",
                "text": "Section A2",
                "version_hash": "v2",
                "domain": DOMAIN_A,
                "page_type": "info_static",
                "crawl_policy_version": POLICY_VER_A,
            },
        ],
    )
    insert_sections(
        TENANT_ID,
        pid_b,
        [
            {
                "section_id": "sec_b_1",
                "text": "Section B1",
                "version_hash": "v1",
                "domain": DOMAIN_B,
                "page_type": "quote_flow",
                "crawl_policy_version": POLICY_VER_B,
            },
            {
                "section_id": "sec_b_2",
                "text": "Section B2",
                "version_hash": "v2",
                "domain": DOMAIN_B,
                "page_type": "quote_flow",
                "crawl_policy_version": POLICY_VER_B,
            },
        ],
    )

    # Query by tenant_id + domain
    assert count_raw_pages_by_domain(TENANT_ID, DOMAIN_A) == 1
    assert count_raw_pages_by_domain(TENANT_ID, DOMAIN_B) == 1
    assert count_sections_by_domain(TENANT_ID, DOMAIN_A) == 2
    assert count_sections_by_domain(TENANT_ID, DOMAIN_B) == 2

    # Query by tenant_id + crawl_policy_version
    assert count_raw_pages_by_crawl_policy_version(TENANT_ID, POLICY_VER_A) == 1
    assert count_raw_pages_by_crawl_policy_version(TENANT_ID, POLICY_VER_B) == 1
    assert count_sections_by_crawl_policy_version(TENANT_ID, POLICY_VER_A) == 2
    assert count_sections_by_crawl_policy_version(TENANT_ID, POLICY_VER_B) == 2
