"""Day 2 acceptance tests: crawl exclusion rules and pipeline behavior."""

import json
from pathlib import Path

import pytest

from apps.api.services.crawl_rules import is_url_allowed
from apps.api.services.pipeline import run_day1_pipeline
from apps.api.services.repo import get_table_counts_for_tenant
from apps.api.tests.conftest import requires_db

# Project root: apps/api/tests -> go up 3 levels
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EXCLUDED_SAMPLES_PATH = PROJECT_ROOT / "eval" / "excluded_samples.json"

# Expected deny reasons (substring match) per URL pattern (quote-flow classification)
EXPECTED_REASONS = {
    "quote.unitedglobalvanline.com/quote": "quote-flow",
    "quote.unitedglobalvanline.com/booking": "quote-flow",
    "quote.unitedglobalvanline.com/get-quote": "quote-flow",
    "quote.unitedglobalvanline.com/wizard": "quote-flow",
    "coasttocoastmovers.com/quote": "quote-flow",
    "coasttocoastmovers.com/get-a-quote": "quote-flow",
    "coasttocoastmovers.com/booking": "quote-flow",
    "coasttocoastmovers.com/estimate": "quote-flow",
    "utm_source": "quote-flow",
    "leadId": "quote-flow",
}


def _expected_reason_for(url: str) -> str:
    for key, reason in EXPECTED_REASONS.items():
        if key in url:
            return reason
    return "quote-flow"  # any excluded sample should have a quote-flow reason


@pytest.fixture
def excluded_urls() -> list[str]:
    with open(EXCLUDED_SAMPLES_PATH) as f:
        return json.load(f)


def test_is_url_allowed_denies_all_samples(excluded_urls) -> None:
    """Each excluded sample URL returns allowed=False with correct reason."""
    for url in excluded_urls:
        allowed, reason = is_url_allowed(url)
        assert allowed is False, f"URL {url} should be denied"
        expected = _expected_reason_for(url)
        assert expected in reason, f"URL {url} expected reason containing {expected!r}, got {reason!r}"


@requires_db
def test_pipeline_on_excluded_url_does_not_increase_db_rows(excluded_urls) -> None:
    """Run pipeline on excluded URL; assert DB row counts do not increase."""
    tenant_id = "tenant_excl_test"
    before = get_table_counts_for_tenant(tenant_id)
    run_day1_pipeline(tenant_id, excluded_urls[0])
    after = get_table_counts_for_tenant(tenant_id)
    assert before == after, f"DB counts must not change: before={before} after={after}"
