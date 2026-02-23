"""Verify Day 4 exclusions: pipeline excludes quote-flow URLs and stores excluded raw_pages.

Deterministic acceptance proof for Day 4.
- Run pipeline on 1 allowed URL + 1 excluded (quote-flow) URL
- Assert excluded URL is skipped (no sectionize/index)
- Assert crawl report includes excluded record with reason
- Assert excluded raw_page row exists

Requires: Postgres running, policy with allowed_domains including both domains
Run: python eval/verify_day4_exclusions.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.db import ensure_tables
from apps.api.services.crawl_report import DEFAULT_REPORT_PATH
from apps.api.services.exclusion import PAGE_TYPE_EXCLUDED
from apps.api.services.pipeline import run_day1_pipeline
from apps.api.services.repo import get_raw_page_counts_by_domain_page_type

TENANT_ID = "coast2coast"

# 1) Allowed informational page (should ingest, sectionize, index)
URL_ALLOWED = "https://coasttocoastmovers.com/about"

# 2) Quote-flow URL (should be excluded by deny_path_prefix /get-quote)
URL_EXCLUDED = "https://quote.unitedglobalvanline.com/get-quote"


def _counts_by_page_type(tenant_id: str) -> dict[str, int]:
    """Aggregate raw_page counts by page_type for tenant."""
    rows = get_raw_page_counts_by_domain_page_type(tenant_id)
    out: dict[str, int] = {}
    for _domain, page_type, count in rows:
        out[page_type] = out.get(page_type, 0) + count
    return out


def main() -> None:
    ensure_tables()

    report_path = DEFAULT_REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)

    print("=== Day 4 Exclusion Proof ===\n")
    print(f"Tenant: {TENANT_ID}\n")

    results: list[dict] = []

    for label, url in [("Allowed", URL_ALLOWED), ("Excluded", URL_EXCLUDED)]:
        print(f"Pipeline: {url}")
        try:
            result = run_day1_pipeline(TENANT_ID, url)
            decision = "excluded" if result.get("excluded") else "allowed"
            reason = result.get("reason", "")
            print(f"  decision: {decision}")
            print(f"  reason: {reason or '-'}")
            results.append({"url": url, "label": label, "decision": decision, "reason": reason})
        except ValueError as e:
            print(f"  ERROR: {e}")
            results.append({"url": url, "label": label, "decision": "error", "reason": str(e)})
        print()

    # Raw page counts by page_type
    counts = _counts_by_page_type(TENANT_ID)
    print("Stored raw_page rows by page_type:")
    for pt, n in sorted(counts.items()):
        print(f"  {pt}: {n}")

    # Assertions
    print("\n=== Assertions ===")
    ok = True

    # 1) Excluded URL is skipped (no sectionize/index)
    excluded_result = next((r for r in results if "Excluded" in r["label"]), None)
    if excluded_result and excluded_result["decision"] == "excluded":
        print("[OK] Excluded URL was skipped (decision=excluded)")
    else:
        print(f"[FAIL] Excluded URL should have decision=excluded, got {excluded_result}")
        ok = False

    # 2) Crawl report includes excluded record with reason
    report_records = []
    if report_path.exists():
        with open(report_path, encoding="utf-8") as f:
            report_records = [json.loads(line) for line in f]
    excluded_record = next((r for r in report_records if r.get("decision") == "excluded" and r.get("reason")), None)
    if excluded_record and excluded_record.get("reason"):
        print(f"[OK] Crawl report includes excluded record with reason={excluded_record['reason'][:60]}...")
    else:
        print(f"[FAIL] Crawl report missing excluded record with reason. Total records: {len(report_records)}")
        ok = False

    # 3) Excluded raw_page row exists
    if PAGE_TYPE_EXCLUDED in counts and counts[PAGE_TYPE_EXCLUDED] >= 1:
        print(f"[OK] Excluded raw_page row exists (ui_flow_excluded count={counts[PAGE_TYPE_EXCLUDED]})")
    else:
        print(f"[FAIL] No raw_page with page_type={PAGE_TYPE_EXCLUDED}. Counts: {counts}")
        ok = False

    if not ok:
        sys.exit(1)
    print("\nDone. Day 4 acceptance proof passed.")


if __name__ == "__main__":
    main()
