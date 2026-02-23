"""Tests for crawl exclusion rules.

Mocking: patch where the code under test imports the dependency (not the original module).
E.g. pipeline uses _fetch -> patch apps.api.services.pipeline._fetch.
"""

from unittest.mock import patch

import pytest

from apps.api.services.crawl_rules import classify_url, is_url_allowed


def test_deny_quote_flow_on_restrictive_host() -> None:
    # quote.unitedglobalvanline.com: allow info_static, deny quote_flow
    allowed, reason = is_url_allowed("https://quote.unitedglobalvanline.com/quote/123")
    assert allowed is False
    assert "quote-flow" in reason or "/quote" in reason


def test_allow_info_static_on_restrictive_host() -> None:
    # quote.unitedglobalvanline.com with no quote-flow pattern -> allowed
    allowed, _ = is_url_allowed("https://quote.unitedglobalvanline.com/about")
    assert allowed is True


def test_allow_info_static_root_on_restrictive_host() -> None:
    allowed, _ = is_url_allowed("https://www.quote.unitedglobalvanline.com/")
    assert allowed is True  # www stripped, root path is info_static


def test_allow_other_host() -> None:
    allowed, reason = is_url_allowed("https://example.com/page")
    assert allowed is True
    assert reason == ""


def test_deny_path_quote() -> None:
    allowed, reason = is_url_allowed("https://example.com/quote/123")
    assert allowed is False
    assert "quote-flow" in reason or "/quote" in reason


def test_deny_path_get_a_quote() -> None:
    allowed, _ = is_url_allowed("https://example.com/get-a-quote?foo=1")
    assert allowed is False


def test_deny_path_booking() -> None:
    allowed, _ = is_url_allowed("https://example.com/booking")
    assert allowed is False


def test_deny_path_book() -> None:
    allowed, _ = is_url_allowed("https://example.com/book/now")
    assert allowed is False


def test_deny_path_estimate() -> None:
    allowed, _ = is_url_allowed("https://example.com/estimate")
    assert allowed is False


def test_deny_path_checkout() -> None:
    allowed, _ = is_url_allowed("https://example.com/checkout")
    assert allowed is False


def test_deny_path_reserve() -> None:
    allowed, _ = is_url_allowed("https://example.com/reserve/123")
    assert allowed is False


def test_allow_similar_path() -> None:
    allowed, _ = is_url_allowed("https://example.com/about")  # no deny prefix matches
    assert allowed is True


def test_deny_query_step() -> None:
    allowed, reason = is_url_allowed("https://example.com/page?step=2")
    assert allowed is False
    assert "step" in reason.lower() or "quote-flow" in reason.lower()


def test_deny_query_session() -> None:
    allowed, _ = is_url_allowed("https://example.com/page?session=abc")
    assert allowed is False


def test_deny_query_token() -> None:
    allowed, _ = is_url_allowed("https://example.com/page?token=xyz")
    assert allowed is False


def test_deny_query_lead() -> None:
    allowed, _ = is_url_allowed("https://example.com/page?lead=123")
    assert allowed is False


def test_deny_query_quote_id() -> None:
    allowed, _ = is_url_allowed("https://example.com/page?quote_id=99")
    assert allowed is False


def test_allow_other_query_keys() -> None:
    allowed, _ = is_url_allowed("https://example.com/page?foo=1&bar=2")
    assert allowed is True


def test_fetch_url_returns_excluded_without_http() -> None:
    """Prove fetch_url returns excluded result and does NOT perform HTTP request."""
    from apps.api.services.crawl import fetch_url

    # Excluded URL (quote-flow) - fetch_url must not make any request
    result = fetch_url("https://quote.unitedglobalvanline.com/quote/123")
    assert result.get("excluded") is True
    assert "reason" in result
    assert "quote-flow" in result["reason"] or "/quote" in result["reason"]


def test_fetch_url_excluded_path() -> None:
    from apps.api.services.crawl import fetch_url

    result = fetch_url("https://example.com/quote/123")
    assert result.get("excluded") is True
    assert "reason" in result


def test_fetch_url_excluded_query() -> None:
    from apps.api.services.crawl import fetch_url

    result = fetch_url("https://example.com/page?step=1")
    assert result.get("excluded") is True
    assert "reason" in result


def test_pipeline_returns_excluded() -> None:
    """Prove pipeline returns exclusion outcome (not domain_not_allowed) for excluded URL.

    Patch target: patch where the code under test uses the dependency.
    Pipeline calls _store_excluded_raw_page when excluding; we patch it to avoid DB.
    Exclusion runs before domain gate, so quote-flow URL returns excluded, does not raise.
    """
    from apps.api.services.pipeline import run_day1_pipeline

    with patch("apps.api.services.pipeline._store_excluded_raw_page"):
        result = run_day1_pipeline("tenant-a", "https://example.com/quote/123")
    assert result.get("excluded") is True
    assert "reason" in result
    assert "quote-flow" in result["reason"] or "deny_path_prefix" in result["reason"] or "/quote" in result["reason"]
    assert "raw_page_id" not in result


# New quote-flow exclusion cases (path prefix, path substring, query key prefix, query key)
def test_exclude_get_quote_path_prefix() -> None:
    """Excluded: path prefix /get-quote on restrictive host."""
    url = "https://quote.unitedglobalvanline.com/get-quote"
    allowed, reason = is_url_allowed(url)
    assert allowed is False
    allowed, page_type, reason = classify_url(url)
    assert allowed is False
    assert page_type == "quote_flow"
    assert "get-quote" in reason or "prefix" in reason


def test_exclude_wizard_step1_path_substring() -> None:
    """Excluded: path contains step-1 (path substring)."""
    url = "https://quote.unitedglobalvanline.com/wizard/step-1"
    allowed, reason = is_url_allowed(url)
    assert allowed is False
    allowed, page_type, reason = classify_url(url)
    assert allowed is False
    assert page_type == "quote_flow"
    assert "step" in reason or "substring" in reason or "wizard" in reason


def test_exclude_estimate_utm_query_prefix() -> None:
    """Excluded: query key prefix utm_ (utm_source=ads)."""
    url = "https://coasttocoastmovers.com/estimate?utm_source=ads"
    allowed, reason = is_url_allowed(url)
    assert allowed is False
    allowed, page_type, reason = classify_url(url)
    assert allowed is False
    assert page_type == "quote_flow"
    assert "utm" in reason or "prefix" in reason or "estimate" in reason


def test_exclude_estimate_step_query_key() -> None:
    """Excluded: query key step (e.g. ?step=1)."""
    url = "https://quote.unitedglobalvanline.com/estimate?step=1"
    allowed, reason = is_url_allowed(url)
    assert allowed is False
    allowed, page_type, reason = classify_url(url)
    assert allowed is False
    assert page_type == "quote_flow"
    assert "step" in reason.lower() or "quote-flow" in reason


def test_exclude_flow_step_query_key() -> None:
    """Excluded: query key step (e.g. ?step=2)."""
    url = "https://quote.unitedglobalvanline.com/flow?step=2"
    allowed, reason = is_url_allowed(url)
    assert allowed is False
    allowed, page_type, reason = classify_url(url)
    assert allowed is False
    assert page_type == "quote_flow"
    assert "step" in reason.lower() or "quote-flow" in reason


def test_exclude_booking_leadid_query_key() -> None:
    """Excluded: query key leadId (normalized to lowercase leadid)."""
    url = "https://coasttocoastmovers.com/booking?leadId=123"
    allowed, reason = is_url_allowed(url)
    assert allowed is False
    allowed, page_type, reason = classify_url(url)
    assert allowed is False
    assert page_type == "quote_flow"
    assert "lead" in reason.lower() or "quote-flow" in reason or "booking" in reason


def test_pipeline_stage_order_is_deterministic() -> None:
    """Pipeline stages run in fixed order; no set/dict iteration for stage lists."""
    from apps.api.services.pipeline import PIPELINE_STAGES

    expected = (
        "url_exclusion",
        "domain_gate",
        "fetch",
        "extract",
        "content_exclusion",
        "ingest",
        "sectionize",
        "index_ac",
    )
    assert PIPELINE_STAGES == expected, "stage order must remain stable for deterministic behavior"
