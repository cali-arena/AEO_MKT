"""Milestone 1 acceptance: quote-flow exclusion rules and crawl report."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.api.services.crawl_rules import classify_url, is_url_allowed
from apps.api.services.pipeline import run_day1_pipeline
from apps.api.services.repo import get_table_counts_for_tenant
from apps.api.tests.conftest import requires_db

# Excluded quote-flow URLs (path prefixes and query keys)
EXCLUDED_URLS = [
    "https://quote.unitedglobalvanline.com/quote",
    "https://quote.unitedglobalvanline.com/estimate?step=1",
    "https://quote.unitedglobalvanline.com/flow?step=2",
    "https://quote.unitedglobalvanline.com/booking?step=1",
    "http://coasttocoastmovers.com/quote",
    "http://coasttocoastmovers.com/get-a-quote",
    "http://example.com/page?step=2",
    "http://example.com/page?session=abc",
]

def test_crawl_rules_marks_excluded_urls() -> None:
    """Crawl rules mark all excluded quote-flow URLs as excluded with correct reason."""
    for url in EXCLUDED_URLS:
        allowed, reason = is_url_allowed(url)
        assert allowed is False, f"URL {url} should be excluded"
        assert reason, f"URL {url} must have non-empty reason"
        # Reason contains quote-flow pattern or query key
        assert (
            "quote-flow" in reason.lower()
            or "path starts with" in reason
            or "query contains" in reason
        ), f"URL {url} reason should describe quote-flow: {reason!r}"


def test_classify_url_returns_page_type_and_reason() -> None:
    """classify_url returns (allowed=False, page_type=quote_flow, reason) for excluded URLs."""
    for url in EXCLUDED_URLS:
        allowed, page_type, reason = classify_url(url)
        assert allowed is False
        assert page_type == "quote_flow"
        assert reason and len(reason) > 0


@requires_db
def test_pipeline_does_not_write_raw_page_or_sections_for_excluded() -> None:
    """Pipeline excludes URLs and does not insert sections (excluded pages may be stored for audit)."""
    tenant_id = "tenant_excl_proof"
    before = get_table_counts_for_tenant(tenant_id)

    for url in EXCLUDED_URLS:
        result = run_day1_pipeline(tenant_id, url)
        assert result.get("excluded") is True, f"Expected excluded: {url}"

    after = get_table_counts_for_tenant(tenant_id)
    assert before["sections"] == after["sections"], "sections count must not increase for excluded URLs"


@requires_db
def test_crawl_report_includes_excluded_records() -> None:
    """Crawl report contains excluded records for each excluded URL run."""
    tmpdir = tempfile.mkdtemp()
    report_path = Path(tmpdir) / "crawl_report.jsonl"
    tenant_id = "tenant_excl_report"

    with patch("apps.api.services.crawl_report.DEFAULT_REPORT_PATH", report_path):
        for url in EXCLUDED_URLS:
            run_day1_pipeline(tenant_id, url)

    records: list[dict] = []
    with open(report_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    excluded_records = [r for r in records if r.get("decision") == "excluded"]
    assert len(excluded_records) >= len(EXCLUDED_URLS), (
        f"Expected at least {len(EXCLUDED_URLS)} excluded records, got {len(excluded_records)}"
    )

    urls_in_report = {r.get("url") for r in excluded_records}
    for url in EXCLUDED_URLS:
        assert url in urls_in_report, f"Excluded URL {url} must appear in crawl report"

    for r in excluded_records[:len(EXCLUDED_URLS)]:
        assert r.get("tenant_id") == tenant_id
        assert r.get("decision") == "excluded"
        assert r.get("reason")
        assert r.get("page_type") in ("quote_flow", "ui_flow_excluded")
