"""Milestone 1 demo: ingest allowed URLs, skip excluded quote-flow, prove via crawl report + DB.

Requires: Postgres running (e.g. docker compose up -d postgres)
Run: python eval/demo_milestone1.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.crawl_report import DEFAULT_REPORT_PATH
from apps.api.services.index_ec import index_ec
from apps.api.services.pipeline import run_day1_pipeline
from apps.api.services.repo import (
    get_raw_page_counts_by_domain_page_type,
    get_section_stats_for_tenant,
    get_table_counts_for_tenant,
)


def load_records(path: Path) -> list[dict]:
    records: list[dict] = []
    if not path.exists():
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


TENANT_ID = "A"
QUERY = "Do they offer long distance moving?"

# Allowed URLs (2 domains): coasttocoastmovers.com + quote.unitedglobalvanline.com info/static
URL_COAST = "https://coasttocoastmovers.com/about"
URL_QUOTE_INFO = "https://quote.unitedglobalvanline.com/company"

HTML_COAST = """
<html><body>
<h1>About Coast to Coast Movers</h1>
<p>We offer long distance moving, local moving, and storage services.
Commercial moving and packing available. Storage solutions in Dallas, TX.
Call 555-123-4567 for a quote. Licensed and insured since 1995.</p>
</body></html>
"""

HTML_QUOTE_INFO = """
<html><body>
<h1>United Global Van Lines</h1>
<p>Informational content about moving tips, company history, and services.
No quote flow here. Static page for company information.</p>
</body></html>
"""

# Excluded quote-flow URLs (from crawl rules)
EXCLUDED_URLS = [
    "https://quote.unitedglobalvanline.com/quote",
    "http://coasttocoastmovers.com/get-a-quote",
    "http://coasttocoastmovers.com/booking?step=1",
]


def main() -> None:
    from apps.api.db import ensure_tables
    ensure_tables()

    client = TestClient(app)
    report_path = Path(DEFAULT_REPORT_PATH)

    print("=== Milestone 1 Demo ===\n")

    # 1) Ingest 2 allowed URLs (mock fetch)
    fetch_responses = {
        URL_COAST: {"final_url": URL_COAST, "status_code": 200, "html": HTML_COAST, "fetched_at": datetime.now(timezone.utc)},
        URL_QUOTE_INFO: {"final_url": URL_QUOTE_INFO, "status_code": 200, "html": HTML_QUOTE_INFO, "fetched_at": datetime.now(timezone.utc)},
    }

    def mock_fetch(url: str) -> dict:
        # Patch target: apps.api.services.pipeline._fetch (where pipeline imports it).
        # Must return {html, final_url, status_code, fetched_at} matching fetch_html_with_meta.
        r = fetch_responses.get(url)
        if r is not None:
            return r
        # Fallback for unexpected URLs - return minimal valid structure
        return {"html": "<html></html>", "final_url": url, "status_code": 200, "fetched_at": datetime.now(timezone.utc)}

    raw_page_ids: list[int] = []
    with patch("apps.api.services.pipeline._fetch", side_effect=mock_fetch):
            print("1. Ingesting 2 allowed URLs (coasttocoastmovers.com + quote.unitedglobalvanline.com info)")
            for url in (URL_COAST, URL_QUOTE_INFO):
                r = run_day1_pipeline(TENANT_ID, url)
                if r.get("excluded"):
                    print(f"   FAIL: {url} excluded: {r.get('reason')}")
                    sys.exit(1)
                raw_page_ids.append(r["raw_page_id"])
                print(f"   OK {url} -> raw_page_id={r['raw_page_id']} sections={len(r.get('section_ids', []))}")

    before_excl = get_table_counts_for_tenant(TENANT_ID)

    # 2) Attempt to ingest excluded URLs; confirm skipped
    print("\n2. Attempting to ingest excluded quote-flow URLs")
    for url in EXCLUDED_URLS:
        r = run_day1_pipeline(TENANT_ID, url)
        assert r.get("excluded"), f"Expected excluded: {url}"
        print(f"   SKIP {url} -> {r.get('reason', '')[:60]}...")

    after_excl = get_table_counts_for_tenant(TENANT_ID)
    assert before_excl["raw_page"] == after_excl["raw_page"], "DB must not grow for excluded URLs"
    print("   OK: raw_page count unchanged (excluded URLs not ingested)")

    # 3) Print post-ingestion stats
    print("\n3. Indexed raw_page by domain + page_type")
    for domain, page_type, cnt in get_raw_page_counts_by_domain_page_type(TENANT_ID):
        print(f"   {domain} | {page_type}: {cnt}")

    stats = get_section_stats_for_tenant(TENANT_ID)
    print(f"\n4. Sections: count={stats['count']} avg_chunk_len={stats['avg_chunk_length']:.0f}")

    excluded_records = [r for r in load_records(report_path) if r.get("tenant_id") == TENANT_ID and r.get("decision") == "excluded"]
    print(f"\n5. Excluded samples (tenant {TENANT_ID}) from crawl_report.jsonl:")
    for r in excluded_records[:10]:
        print(f"   {r.get('url', '?')}")
        print(f"     reason: {r.get('reason', '?')[:70]}")

    # 6) Retrieve AC
    print("\n6. POST /retrieve/ac (top 3)")
    ac_resp = client.post("/retrieve/ac", json={"query": QUERY, "k": 3}, headers={"Authorization": f"Bearer tenant:{TENANT_ID}"})
    assert ac_resp.status_code == 200, ac_resp.text
    ac_data = ac_resp.json()
    for i, c in enumerate(ac_data.get("candidates", [])[:3], 1):
        sid = c.get("section_id", "?")[:24]
        url_short = (c.get("url", "") or "?")[:45]
        print(f"   [{i}] {sid}... | {url_short}...")

    # 7) Index EC on ingested raw_pages
    print("\n7. index_ec on ingested pages")
    for pid in raw_page_ids:
        ec_result = index_ec(TENANT_ID, pid)
        print(f"   raw_page_id={pid} entities={ec_result['entities_count']} relations={ec_result['relations_count']}")

    # 8) Retrieve EC
    print("\n8. POST /retrieve/ec (top 3)")
    ec_resp = client.post("/retrieve/ec", json={"query": QUERY, "k": 3}, headers={"Authorization": f"Bearer tenant:{TENANT_ID}"})
    assert ec_resp.status_code == 200, ec_resp.text
    ec_data = ec_resp.json()
    for i, c in enumerate(ec_data.get("candidates", [])[:3], 1):
        sid = (c.get("section_id", "?") or "?")[:24]
        snippet = (c.get("snippet", "") or "")[:50]
        print(f"   [{i}] section={sid}... | {snippet}...")

    # 9) Answer
    print("\n9. POST /answer")
    ans_resp = client.post("/answer", json={"query": QUERY}, headers={"Authorization": f"Bearer tenant:{TENANT_ID}"})
    assert ans_resp.status_code == 200, ans_resp.text
    ans_data = ans_resp.json()
    print(f"   refused={ans_data.get('refused')} refusal_reason={ans_data.get('refusal_reason') or '-'}")
    for i, claim in enumerate(ans_data.get("claims", [])[:3], 1):
        txt = (claim.get("text") or "")[:80]
        if len(claim.get("text") or "") > 80:
            txt += "..."
        print(f"   claim[{i}]: {txt} | evidence_ids={claim.get('evidence_ids', [])[:3]}")

    print("\n=== Milestone 1 demo complete ===")


if __name__ == "__main__":
    main()
