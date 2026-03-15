"""Tests for content exclusion: registered homepage override and quote/form subdomain protection."""

from datetime import datetime
from unittest.mock import patch

import pytest

from apps.api.services.exclusion import ui_flow_heuristic
from apps.api.services.pipeline import (
    _should_override_ui_form_for_registered_homepage,
    run_day1_pipeline,
)
from apps.api.tests.conftest import requires_db

# Form-heavy HTML that triggers ui_form_heuristic when text is short
FORM_HEAVY_HTML = """
<!DOCTYPE html><html><head><title>Home</title></head><body>
<form action="/submit" method="post">
  <input type="text" name="name" aria-label="Your name" />
  <input type="email" name="email" aria-label="Email" />
  <input type="tel" name="phone" />
  <select name="state"><option>TX</option></select>
  <textarea name="notes"></textarea>
  <input type="hidden" name="token" />
  <button type="submit">Submit</button>
</form>
<p>Get a quote today.</p>
</body></html>
"""
# Short extracted text triggers heuristic (text_len < 600, tag_hits >= 12)
SHORT_BODY_TEXT = "Get a quote today."


def _make_fetch_result(html: str, final_url: str) -> dict:
    return {
        "html": html,
        "final_url": final_url,
        "status_code": 200,
        "fetched_at": datetime.utcnow(),
    }


def test_override_registered_homepage_root_same_domain() -> None:
    """Override applies for requested domain homepage (root path) when reason is ui_form_heuristic."""
    assert _should_override_ui_form_for_registered_homepage(
        "adaptedtech.com.br",
        "adaptedtech.com.br",
        "https://adaptedtech.com.br/",
        "ui_form_heuristic:text_len=100,tag_hits=15,density=0.05",
    ) is True


def test_no_override_quote_subdomain() -> None:
    """No override for quote subdomain root (quote.example.com)."""
    assert _should_override_ui_form_for_registered_homepage(
        "quote.example.com",
        "quote.example.com",
        "https://quote.example.com/",
        "ui_form_heuristic:text_len=100,tag_hits=15,density=0.05",
    ) is False


def test_no_override_non_root_path() -> None:
    """No override for non-homepage path on same domain."""
    assert _should_override_ui_form_for_registered_homepage(
        "adaptedtech.com.br",
        "adaptedtech.com.br",
        "https://adaptedtech.com.br/contact",
        "ui_form_heuristic:text_len=100,tag_hits=15,density=0.05",
    ) is False


def test_no_override_other_reason() -> None:
    """No override when exclusion reason is not ui_form_heuristic."""
    assert _should_override_ui_form_for_registered_homepage(
        "adaptedtech.com.br",
        "adaptedtech.com.br",
        "https://adaptedtech.com.br/",
        "deny_path_prefix:/quote",
    ) is False


@requires_db
def test_registered_homepage_form_heavy_not_excluded() -> None:
    """Main homepage of requested domain that is CTA/form heavy should still ingest (override)."""
    tenant_id = "tenant_homepage_override"
    url = "https://adaptedtech.com.br/"
    # Normalized text from extraction will be short; use HTML that yields short text
    fetch_result = _make_fetch_result(FORM_HEAVY_HTML, url)
    # Ensure heuristic would exclude: short text + form-heavy
    _, _, details = ui_flow_heuristic(FORM_HEAVY_HTML, SHORT_BODY_TEXT)
    assert details["text_len"] < 600
    assert details["tag_hits"] >= 12

    with patch("apps.api.services.pipeline._fetch", return_value=fetch_result):
        result = run_day1_pipeline(tenant_id, url)

    assert result.get("excluded") is not True, (
        "Registered domain homepage should not be excluded by ui_form_heuristic (override)"
    )
    assert "raw_page_id" in result or "excluded" not in result


@requires_db
def test_quote_subdomain_root_still_excluded() -> None:
    """Quote/form subdomain root (e.g. quote.example.com/) should still be excluded (no override)."""
    tenant_id = "tenant_quote_subdomain"
    url = "https://quote.example.com/"
    fetch_result = _make_fetch_result(FORM_HEAVY_HTML, url)

    with patch("apps.api.services.pipeline._fetch", return_value=fetch_result):
        result = run_day1_pipeline(tenant_id, url)

    assert result.get("excluded") is True
    assert "ui_form_heuristic" in (result.get("reason") or "")


@requires_db
def test_non_root_form_heavy_still_excluded() -> None:
    """Non-homepage page (same domain) that is form-heavy should still be excluded (no override)."""
    tenant_id = "tenant_non_root"
    url = "https://adaptedtech.com.br/some/form-page"
    fetch_result = _make_fetch_result(FORM_HEAVY_HTML, url)

    with patch("apps.api.services.pipeline._fetch", return_value=fetch_result):
        result = run_day1_pipeline(tenant_id, url)

    assert result.get("excluded") is True
    assert "ui_form_heuristic" in (result.get("reason") or "")
