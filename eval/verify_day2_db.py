"""Verify domain and crawl_policy_version inserts and queries.

Requires: Postgres running (e.g. docker compose up -d postgres)
Run: python eval/verify_day2_db.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.db import ensure_tables
from apps.api.services.repo import (
    count_raw_pages_by_crawl_policy_version,
    count_raw_pages_by_domain,
    count_sections_by_crawl_policy_version,
    count_sections_by_domain,
    insert_raw_page,
    insert_sections,
)

TENANT_ID = f"verify_day2_tenant_{int(time.time())}"
DOMAIN_A = "example-a.com"
DOMAIN_B = "example-b.com"
POLICY_VER_A = "a1b2c3d4e5f6"
POLICY_VER_B = "f6e5d4c3b2a1"


def main() -> None:
    ensure_tables()

    print("=== Day 2 DB verification: domain + crawl_policy_version ===\n")

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
    print(f"Inserted raw_page A (id={pid_a}) domain={DOMAIN_A} policy_version={POLICY_VER_A}")
    print(f"Inserted raw_page B (id={pid_b}) domain={DOMAIN_B} policy_version={POLICY_VER_B}")

    # Insert 2 sections per page (with domain/page_type/crawl_policy_version)
    insert_sections(
        TENANT_ID,
        pid_a,
        [
            {"section_id": "sec_a_1", "text": "Section A1", "version_hash": "v1", "domain": DOMAIN_A, "page_type": "info_static", "crawl_policy_version": POLICY_VER_A},
            {"section_id": "sec_a_2", "text": "Section A2", "version_hash": "v2", "domain": DOMAIN_A, "page_type": "info_static", "crawl_policy_version": POLICY_VER_A},
        ],
    )
    insert_sections(
        TENANT_ID,
        pid_b,
        [
            {"section_id": "sec_b_1", "text": "Section B1", "version_hash": "v1", "domain": DOMAIN_B, "page_type": "quote_flow", "crawl_policy_version": POLICY_VER_B},
            {"section_id": "sec_b_2", "text": "Section B2", "version_hash": "v2", "domain": DOMAIN_B, "page_type": "quote_flow", "crawl_policy_version": POLICY_VER_B},
        ],
    )
    print("Inserted 2 sections per page\n")

    # Query by tenant_id + domain
    raw_count_domain_a = count_raw_pages_by_domain(TENANT_ID, DOMAIN_A)
    raw_count_domain_b = count_raw_pages_by_domain(TENANT_ID, DOMAIN_B)
    sec_count_domain_a = count_sections_by_domain(TENANT_ID, DOMAIN_A)
    sec_count_domain_b = count_sections_by_domain(TENANT_ID, DOMAIN_B)

    print("a) Filter by tenant_id + domain:")
    print(f"   raw_page domain={DOMAIN_A}: {raw_count_domain_a}")
    print(f"   raw_page domain={DOMAIN_B}: {raw_count_domain_b}")
    print(f"   sections domain={DOMAIN_A}: {sec_count_domain_a}")
    print(f"   sections domain={DOMAIN_B}: {sec_count_domain_b}")

    # Query by tenant_id + crawl_policy_version
    raw_count_policy_a = count_raw_pages_by_crawl_policy_version(TENANT_ID, POLICY_VER_A)
    raw_count_policy_b = count_raw_pages_by_crawl_policy_version(TENANT_ID, POLICY_VER_B)
    sec_count_policy_a = count_sections_by_crawl_policy_version(TENANT_ID, POLICY_VER_A)
    sec_count_policy_b = count_sections_by_crawl_policy_version(TENANT_ID, POLICY_VER_B)

    print("\nb) Filter by tenant_id + crawl_policy_version:")
    print(f"   raw_page policy={POLICY_VER_A}: {raw_count_policy_a}")
    print(f"   raw_page policy={POLICY_VER_B}: {raw_count_policy_b}")
    print(f"   sections policy={POLICY_VER_A}: {sec_count_policy_a}")
    print(f"   sections policy={POLICY_VER_B}: {sec_count_policy_b}")

    # Assert expected counts
    assert raw_count_domain_a == 1, f"Expected 1 raw_page for domain A, got {raw_count_domain_a}"
    assert raw_count_domain_b == 1, f"Expected 1 raw_page for domain B, got {raw_count_domain_b}"
    assert sec_count_domain_a == 2, f"Expected 2 sections for domain A, got {sec_count_domain_a}"
    assert sec_count_domain_b == 2, f"Expected 2 sections for domain B, got {sec_count_domain_b}"
    assert raw_count_policy_a == 1, f"Expected 1 raw_page for policy A, got {raw_count_policy_a}"
    assert raw_count_policy_b == 1, f"Expected 1 raw_page for policy B, got {raw_count_policy_b}"
    assert sec_count_policy_a == 2, f"Expected 2 sections for policy A, got {sec_count_policy_a}"
    assert sec_count_policy_b == 2, f"Expected 2 sections for policy B, got {sec_count_policy_b}"

    print("\nOK All counts match expected. Verification passed.")


if __name__ == "__main__":
    main()
