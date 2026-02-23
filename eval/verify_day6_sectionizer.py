"""Verify Day 6 sectionizer: ingest, sectionize+persist, rerun => identical section_ids.

Done when proof for Day 6.
- Ingest one URL (or use fixture)
- Run sectionize + persist
- Print total sections N, first 3 with section_id, heading_path, len(text), version_hash, domain, page_type, crawl_policy_version
- Rerun sectionize on same content and assert section_ids identical

Requires: Postgres running, policy with allowed_domains
Run: python eval/verify_day6_sectionizer.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.db import ensure_tables
from apps.api.services.extract import extract_main_text, extract_title
from apps.api.services.normalize import content_hash, normalize_text
from apps.api.services.page_type import infer_page_type
from apps.api.services.pipeline import run_day1_pipeline
from apps.api.services.policy import crawl_policy_version as get_crawl_policy_version
from apps.api.services.policy import load_policy
from apps.api.services.repo import get_sections_by_raw_page_id
from apps.api.services.sectionize import sectionize_and_persist
from apps.api.services.url_utils import canonicalize_url

TENANT_ID = "coast2coast"

HTML = """<!DOCTYPE html>
<html><head><title>Sectionizer Test</title></head>
<body>
<h1>Main Title</h1>
<p>Intro paragraph for the main section.</p>
<h2>Section A</h2>
<p>Content for section A with some details.</p>
<h2>Section B</h2>
<p>Content for section B.</p>
</body></html>"""


def main() -> None:
    ensure_tables()

    # Unique URL per run so we always get fresh ingest + sectionize (no unchanged skip)
    ts = int(datetime.now(timezone.utc).timestamp())
    URL = f"https://coasttocoastmovers.com/sectionizer-test-{ts}"

    print("=== Day 6 Sectionizer Proof ===\n")
    print(f"Tenant: {TENANT_ID}")
    print(f"URL: {URL}\n")

    fetch = {
        "final_url": URL,
        "status_code": 200,
        "html": HTML,
        "fetched_at": datetime.now(timezone.utc),
    }

    with patch("apps.api.services.pipeline._fetch", return_value=fetch):
        result = run_day1_pipeline(TENANT_ID, URL)

    if result.get("excluded"):
        print(f"ERROR: URL excluded: {result.get('reason')}")
        sys.exit(1)

    raw_page_id = result.get("raw_page_id")
    normalized = normalize_text(extract_main_text(HTML))
    ch = content_hash(normalized)
    _, domain = canonicalize_url(URL)
    page_type = infer_page_type(URL, title=extract_title(HTML), text=normalized)
    policy_ver = get_crawl_policy_version(load_policy())

    # Pipeline already sectionized; get sections
    sections = get_sections_by_raw_page_id(TENANT_ID, raw_page_id)
    n = len(sections)
    print(f"Total sections: {n}\n")
    print("First 3 sections:")
    for s in sections[:3]:
        print(f"  section_id={s['section_id']}")
        print(f"    heading_path={s.get('heading_path', '')!r}")
        print(f"    len(text)={len(s.get('text') or '')}")
        print(f"    version_hash={s.get('version_hash', '')}")
        print(f"    domain={s.get('domain')} page_type={s.get('page_type')} crawl_policy_version={s.get('crawl_policy_version')}")

    section_ids_1 = [s["section_id"] for s in sections]

    sectionize_and_persist(
        TENANT_ID,
        raw_page_id,
        URL,
        normalized,
        html=HTML,
        raw_page_content_hash=ch,
        domain=domain,
        page_type=page_type,
        crawl_policy_version=policy_ver,
    )
    sections_2 = get_sections_by_raw_page_id(TENANT_ID, raw_page_id)
    section_ids_2 = [s["section_id"] for s in sections_2]

    print("\n=== Assertion ===")
    if section_ids_1 == section_ids_2:
        print("[OK] Rerun sectionize on same content => section_ids identical")
    else:
        print(f"[FAIL] section_ids differ: {section_ids_1[:3]} vs {section_ids_2[:3]}")
        sys.exit(1)

    print("\nDone. Day 6 sectionizer proof passed.")


if __name__ == "__main__":
    main()
