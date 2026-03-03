"""Smoke check for domain ingestion: ensures raw_page rows exist after ingest."""

from __future__ import annotations

import argparse
import json

from apps.api.services.ingest import ingest_domain_sync
from apps.api.services.repo import count_raw_pages_by_domain


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ingest_domain_sync and verify raw_page count > 0")
    parser.add_argument("--tenant", required=True, help="Tenant ID")
    parser.add_argument("--domain", required=True, help="Domain to ingest, e.g. example.com")
    args = parser.parse_args()

    summary = ingest_domain_sync(args.tenant, args.domain)
    raw_count = count_raw_pages_by_domain(args.tenant, summary["domain"])

    output = {
        "ok": raw_count > 0,
        "tenant_id": args.tenant,
        "domain": summary["domain"],
        "raw_page_count": raw_count,
        "summary": summary,
    }
    print(json.dumps(output, ensure_ascii=True))
    if raw_count <= 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
