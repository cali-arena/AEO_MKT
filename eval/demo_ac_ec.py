"""Day 4 demo: proves AC vs EC separation. Pipeline + index_ec + /retrieve/ac + /retrieve/ec.

Requires: Postgres running (e.g. docker compose up -d postgres)
Run: python eval/demo_ac_ec.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.index_ec import index_ec
from apps.api.services.pipeline import run_day1_pipeline

client = TestClient(app)

TENANT_A = "tenant_demo_ac_ec"
QUERY = "Do they offer long distance moving?"
URL = "https://coasttocoastmovers.com/services"  # domain must be in policy allowed_domains


def main() -> None:
    from apps.api.db import ensure_tables
    ensure_tables()

    print("=== AC vs EC Separation Demo (Day 4) ===\n")

    html = """
    <html><body>
    <p>We offer long distance moving and local moving services.
    Commercial moving and packing available. Storage solutions in Dallas, TX.
    Call 555-123-4567 for a quote.</p>
    </body></html>
    """
    # Patch target: apps.api.services.pipeline._fetch (where pipeline imports it).
    # Must return {html, final_url, status_code, fetched_at} matching fetch_html_with_meta.
    mock_fetch = patch(
        "apps.api.services.pipeline._fetch",
        return_value={
            "html": html,
            "final_url": URL,
            "status_code": 200,
            "fetched_at": datetime.now(timezone.utc),
        },
    )

    with mock_fetch:
        print(f"1. Running pipeline for tenant {TENANT_A!r} on {URL}")
        result = run_day1_pipeline(TENANT_A, URL)
        if result.get("excluded"):
            print(f"   EXCLUDED: {result.get('reason')}")
            sys.exit(1)
        raw_page_id = result["raw_page_id"]
        print(f"   raw_page_id={raw_page_id} sections={len(result.get('section_ids', []))}")

        print(f"\n2. Running index_ec for raw_page_id={raw_page_id}")
        ec_result = index_ec(TENANT_A, raw_page_id)
        print(f"   entities={ec_result['entities_count']} relations={ec_result['relations_count']}")

    print(f"\n3. POST /retrieve/ac  query={QUERY!r}")
    ac_resp = client.post(
        "/retrieve/ac",
        json={"query": QUERY, "k": 10},
        headers={"Authorization": f"Bearer tenant:{TENANT_A}"},
    )
    assert ac_resp.status_code == 200, ac_resp.text
    ac_data = ac_resp.json()

    print(f"\n4. POST /retrieve/ec  query={QUERY!r}")
    ec_resp = client.post(
        "/retrieve/ec",
        json={"query": QUERY, "k": 10},
        headers={"Authorization": f"Bearer tenant:{TENANT_A}"},
    )
    assert ec_resp.status_code == 200, ec_resp.text
    ec_data = ec_resp.json()

    print("\n" + "=" * 60)
    print("AC results (section-based, vector search):")
    print("  debug:", ac_data.get("debug", {}))
    for i, c in enumerate(ac_data.get("candidates", []), 1):
        print(f"  [{i}] section_id={c['section_id']} url={c['url']}")
        print(f"      snippet: {c['snippet'][:100]}...")

    print("\n" + "=" * 60)
    print("EC results (entity-based, text search on entities.name):")
    print("  debug:", ec_data.get("debug", {}))
    for i, c in enumerate(ec_data.get("candidates", []), 1):
        print(f"  [{i}] section_id={c['section_id']}")
        print(f"      snippet (from evidence.quote_span): {c['snippet'][:100]}...")

    print("\n=== Demo complete ===")


if __name__ == "__main__":
    main()
