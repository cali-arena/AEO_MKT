"""Print crawl report summary: counts by decision, domain, page_type; top excluded samples."""

import json
from collections import Counter
from pathlib import Path

DEFAULT_REPORT_PATH = Path(__file__).resolve().parent / "reports" / "crawl_report.jsonl"


def load_records(path: Path) -> list[dict]:
    """Load JSONL records from file."""
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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Print crawl report summary")
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"Path to JSONL report (default: {DEFAULT_REPORT_PATH})",
    )
    args = parser.parse_args()

    records = load_records(args.path)
    if not records:
        print("No records in report.")
        return

    # Counts by decision
    by_decision = Counter(r.get("decision", "?") for r in records)
    print("=== By decision ===")
    for k, v in sorted(by_decision.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    # Counts by domain
    by_domain = Counter(r.get("domain", "") or "(empty)" for r in records)
    print("\n=== By domain ===")
    for k, v in by_domain.most_common(20):
        print(f"  {k}: {v}")

    # Counts by page_type
    by_page_type = Counter(r.get("page_type", "") or "(empty)" for r in records)
    print("\n=== By page_type ===")
    for k, v in sorted(by_page_type.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    # Top 10 excluded samples with reasons
    excluded = [r for r in records if r.get("decision") == "excluded"]
    if excluded:
        print("\n=== Top 10 excluded samples (with reasons) ===")
        for r in excluded[:10]:
            url = r.get("url", r.get("canonical_url", "?"))
            reason = r.get("reason", "?")
            print(f"  {url}")
            print(f"    reason: {reason}")
    else:
        print("\n=== No excluded samples ===")


if __name__ == "__main__":
    main()
