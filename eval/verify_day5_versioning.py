"""Verify Day 5 versioning: same content => no new row; changed content => version increment.

Deterministic acceptance proof for Day 5.
- Run pipeline twice with same content => raw_page count unchanged, same raw_page_id
- Simulate modified content (monkeypatch fetch) => raw_page count +1, version increments
- Print raw_page_id, version, content_hash[:8], changed flag

Requires: Postgres running, policy with allowed_domains
Run: python eval/verify_day5_versioning.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.db import ensure_tables
from apps.api.services.pipeline import run_day1_pipeline
from apps.api.services.repo import get_latest_raw_page_by_canonical_url, get_table_counts_for_tenant
from apps.api.services.url_utils import canonicalize_url

TENANT_ID = "coast2coast"

# URL must be in allowed_domains (coasttocoastmovers.com)
URL = "https://coasttocoastmovers.com/services"

# Fixture HTML - same content for runs 1 & 2
HTML_SAME = """<!DOCTYPE html>
<html><head><title>Services Page</title></head>
<body><article><p>We offer moving services nationwide.</p><p>Full service packing and transport.</p></article></body></html>"""

# Modified HTML - triggers new row and version increment
HTML_MODIFIED = """<!DOCTYPE html>
<html><head><title>Services Page</title></head>
<body><article><p>We offer moving services nationwide.</p><p>Full service packing, transport, and storage.</p></article></body></html>"""


def _make_fetch_result(html: str, url: str = URL):
    canonical, domain = canonicalize_url(url)
    return {
        "html": html,
        "final_url": url,
        "status_code": 200,
        "fetched_at": datetime.now(timezone.utc),
    }


def main() -> None:
    ensure_tables()

    print("=== Day 5 Versioning Proof ===\n")
    print(f"Tenant: {TENANT_ID}")
    print(f"URL: {URL}\n")

    counts = get_table_counts_for_tenant(TENANT_ID)
    count_before = counts["raw_page"]

    # 1) Run pipeline twice with same content (monkeypatch fetch)
    fetch_same = _make_fetch_result(HTML_SAME)
    with patch("apps.api.services.pipeline._fetch", return_value=fetch_same):
        r1 = run_day1_pipeline(TENANT_ID, URL)
    raw_page_id_1 = r1.get("raw_page_id")
    changed_1 = not r1.get("unchanged", False)

    with patch("apps.api.services.pipeline._fetch", return_value=fetch_same):
        r2 = run_day1_pipeline(TENANT_ID, URL)
    raw_page_id_2 = r2.get("raw_page_id")
    changed_2 = not r2.get("unchanged", False)

    count_after_same = get_table_counts_for_tenant(TENANT_ID)["raw_page"]
    latest = get_latest_raw_page_by_canonical_url(TENANT_ID, URL)

    print("Run 1 (same):")
    print(f"  raw_page_id={raw_page_id_1} version={latest['version']} content_hash={latest['content_hash'][:8] if latest and latest.get('content_hash') else '-'} changed={changed_1}")
    print("Run 2 (same content):")
    print(f"  raw_page_id={raw_page_id_2} version={latest['version']} content_hash={latest['content_hash'][:8] if latest and latest.get('content_hash') else '-'} changed={changed_2}")

    # Assert: no new row, same raw_page_id
    ok = True
    if count_after_same == count_before + 1:  # Only 1 new row from run 1; run 2 added none
        print("\n[OK] Same content twice: raw_page count increased by 1 (run 1 only)")
    else:
        print(f"\n[FAIL] Same content twice: expected count {count_before}+1={count_before+1}, got {count_after_same}")
        ok = False

    if raw_page_id_1 == raw_page_id_2:
        print("[OK] Same content: raw_page_id unchanged")
    else:
        print(f"[FAIL] Same content: raw_page_id should match, got {raw_page_id_1} vs {raw_page_id_2}")
        ok = False

    # 2) Run pipeline with modified content
    version_before = latest["version"] if latest else 0
    fetch_modified = _make_fetch_result(HTML_MODIFIED)
    with patch("apps.api.services.pipeline._fetch", return_value=fetch_modified):
        r3 = run_day1_pipeline(TENANT_ID, URL)
    raw_page_id_3 = r3.get("raw_page_id")
    changed_3 = not r3.get("unchanged", False)
    latest2 = get_latest_raw_page_by_canonical_url(TENANT_ID, URL)
    count_after_modified = get_table_counts_for_tenant(TENANT_ID)["raw_page"]

    print("\nRun 3 (modified content):")
    print(f"  raw_page_id={raw_page_id_3} version={latest2['version']} content_hash={latest2['content_hash'][:8] if latest2 and latest2.get('content_hash') else '-'} changed={changed_3}")

    if count_after_modified == count_after_same + 1:
        print("[OK] Modified content: raw_page count increased by 1")
    else:
        print(f"[FAIL] Modified content: expected count {count_after_same}+1, got {count_after_modified}")
        ok = False

    if latest2 and latest2["version"] == version_before + 1:
        print(f"[OK] Modified content: version incremented {version_before} -> {latest2['version']}")
    else:
        print(f"[FAIL] Modified content: version should be {version_before}+1, got {latest2['version'] if latest2 else 'None'}")
        ok = False

    if raw_page_id_3 != raw_page_id_1:
        print("[OK] Modified content: new raw_page_id (new row)")
    else:
        print(f"[FAIL] Modified content: raw_page_id should differ from run 1")
        ok = False

    if not ok:
        sys.exit(1)
    print("\nDone. Day 5 acceptance proof passed.")


if __name__ == "__main__":
    main()
