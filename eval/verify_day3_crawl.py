"""Verify Day 3 crawl integration: crawl -> persist with canonical_url, domain, crawl_policy_version, content_hash.

Requires: Postgres running, policy with allowed_domains
Run: python eval/verify_day3_crawl.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.db import ensure_tables
from apps.api.services.crawl import crawl_and_persist

TENANT_ID = "coast2coast"
URLS = [
    "https://coasttocoastmovers.com/about",
    "https://quote.unitedglobalvanline.com/company",
]


def main() -> None:
    ensure_tables()

    print("=== Day 3 Crawl Integration ===\n")

    for url in URLS:
        print(f"Crawling: {url}")
        try:
            result = crawl_and_persist(TENANT_ID, url)
            print(f"  canonical_url: {result['canonical_url']}")
            print(f"  domain: {result['domain']}")
            print(f"  crawl_policy_version: {result['crawl_policy_version']}")
            print(f"  content_hash[:8]: {result['content_hash'][:8]}")
            print()
        except ValueError as e:
            print(f"  ERROR: {e}")
            continue

    print("Done. Check DB for raw_page rows.")


if __name__ == "__main__":
    main()
