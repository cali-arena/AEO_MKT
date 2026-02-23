"""Print acceptance report: crawl results, chunk stats, retrieval sanity checks, leakage test.

Requires: Postgres, and data from demo_milestone1.py (or similar pipeline runs)
Run: python eval/print_acceptance_report.py [--tenant A] [--report eval/reports/crawl_report.jsonl]
"""

import argparse
import os

# Reduce HuggingFace/sentence-transformers verbosity
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.services.crawl_report import DEFAULT_REPORT_PATH
from apps.api.services.repo import (
    get_raw_page_counts_by_domain_page_type,
    get_section_by_id,
    get_section_stats_for_tenant,
)
from apps.api.services.retrieve import retrieve_ac
from apps.api.services.span import select_quote_span

DEFAULT_TENANT = "A"
QUERIES = [
    "Do they offer long distance moving?",
    "What storage options are available?",
    "Commercial moving services",
]

QUOTE_DOMAIN = "quote.unitedglobalvanline.com"
COAST_DOMAIN = "coasttocoastmovers.com"


def _load_crawl_records(path: Path) -> list[dict]:
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


def _categorize_reason(reason: str) -> str:
    r = (reason or "").lower()
    if "path" in r or "prefix" in r or "route" in r or "flow" in r:
        return "flow route"
    if "session" in r or "token" in r or "query" in r or "key" in r:
        return "session/token params"
    if "form" in r or "heuristic" in r or "fetch" in r:
        return "form UI heuristic"
    return "other"


def _run_leakage_tests() -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "apps/api/tests/test_leakage.py", "-v", "--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=Path(__file__).resolve().parent.parent,
        )
        if result.returncode == 0:
            return "PASS"
        return "FAIL"
    except Exception as e:
        return f"ERROR ({e})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Print acceptance report")
    parser.add_argument("--tenant", default=DEFAULT_TENANT, help="Tenant ID")
    parser.add_argument("--report", type=Path, default=Path(DEFAULT_REPORT_PATH), help="Crawl report JSONL path")
    parser.add_argument("--run-demo", action="store_true", help="Run demo_milestone1 first to populate data")
    args = parser.parse_args()

    if args.run_demo:
        project_root = Path(__file__).resolve().parent.parent
        print("Running demo_milestone1 to populate data...\n")
        subprocess.run(
            [sys.executable, "eval/demo_milestone1.py"],
            cwd=project_root,
            check=True,
        )
        print("\n--- Acceptance Report ---\n")

    tenant_id = args.tenant
    report_path = args.report

    records = _load_crawl_records(report_path)
    tenant_records = [r for r in records if r.get("tenant_id") == tenant_id]

    # A) Crawl results
    allowed_by_domain: dict[str, int] = {}
    for domain, page_type, cnt in get_raw_page_counts_by_domain_page_type(tenant_id):
        if domain not in ("(empty)", ""):
            allowed_by_domain[domain] = allowed_by_domain.get(domain, 0) + cnt

    coast_idx = allowed_by_domain.get(COAST_DOMAIN, 0)
    quote_idx = allowed_by_domain.get(QUOTE_DOMAIN, 0)

    excluded_quote = [
        r for r in tenant_records
        if r.get("decision") == "excluded" and (r.get("domain") or "").find("quote.united") >= 0
    ]
    z_excluded = len(excluded_quote)

    reason_cats: Counter[str] = Counter()
    for r in excluded_quote:
        reason_cats[_categorize_reason(r.get("reason", ""))] += 1
    top_reasons = [f"{k} ({v})" for k, v in reason_cats.most_common(5) if k != "other"]

    print("A) Crawl results")
    print(f"  {COAST_DOMAIN}: {coast_idx} pages indexed")
    print(f"  {QUOTE_DOMAIN}: {quote_idx} pages indexed")
    print(f"  quote domain excluded: {z_excluded} pages (ui_flow_excluded)")
    print(f"  top exclusion reasons: {', '.join(top_reasons) or 'none'}")
    print()

    # B) Chunk stats
    stats = get_section_stats_for_tenant(tenant_id)
    n = stats["count"]
    a = int(stats["avg_chunk_length"])
    mn = stats.get("min_chunk_length", 0)
    mx = stats.get("max_chunk_length", 0)

    print("B) Chunk stats")
    print(f"  total sections: {n}")
    print(f"  avg chars/section: {a}")
    print(f"  min/max: {mn} / {mx}")
    print()

    # C) Retrieval sanity checks
    print("C) Retrieval sanity checks (3 queries)")
    for q in QUERIES:
        print(f'  Q: "{q}"')
        resp = retrieve_ac(tenant_id, q, k=3)
        for i, c in enumerate(resp.candidates[:3], 1):
            section = get_section_by_id(tenant_id, c.section_id)
            text = (section.get("text") or "") if section else ""
            quote_span, _, _ = select_quote_span(text, q, max_len=280)
            quote_display = (quote_span or c.snippet or "")[:300].strip()
            if len(quote_span or "") > 300:
                quote_display = quote_display + "..."
            print(f"    - {i}) {c.url or '?'} | {c.section_id} | score={c.merged_score}")
            print(f'        evidence: "{quote_display}"')
        if not resp.candidates:
            print("    (no results)")
        print()

    # D) Leakage test
    leakage_status = _run_leakage_tests()
    print("D) Leakage test status")
    print(f"  {leakage_status}")


if __name__ == "__main__":
    main()
