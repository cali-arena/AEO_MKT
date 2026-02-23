"""Tests for exclusion form-UI heuristic."""

import pytest

from apps.api.services.exclusion import should_exclude, ui_flow_heuristic

# Fake HTML: many form elements, short visible text
FORM_HEAVY_HTML = """
<form action="/submit" method="post">
  <input type="text" name="name" aria-label="Your name" />
  <input type="email" name="email" aria-label="Email" />
  <input type="tel" name="phone" />
  <select name="state"><option>TX</option></select>
  <textarea name="notes"></textarea>
  <input type="hidden" name="token" />
  <button type="submit">Submit</button>
</form>
"""

SHORT_TEXT = "Enter your info."


def test_ui_flow_heuristic_excludes_form_heavy_short_text() -> None:
    """Form-heavy HTML + short text triggers exclusion."""
    excluded, reason = ui_flow_heuristic(FORM_HEAVY_HTML, SHORT_TEXT)
    assert excluded is True
    assert "ui_form_heuristic" in reason
    assert "text_len=" in reason
    assert "tag_hits=" in reason
    assert "density=" in reason


def test_ui_flow_heuristic_allows_long_text() -> None:
    """Long text with same form density may be allowed (depends on thresholds)."""
    long_text = "A" * 1500  # Above 1200
    excluded, reason = ui_flow_heuristic(FORM_HEAVY_HTML, long_text)
    # density = tag_hits / 1500. With ~15 tags, density ~ 0.01 < 0.03, so allowed
    assert excluded is False


def test_should_exclude_calls_heuristic_when_html_text_provided() -> None:
    """should_exclude runs form heuristic when html and text are passed."""
    excluded, reason, page_type = should_exclude(
        "https://example.com/info",
        html=FORM_HEAVY_HTML,
        text=SHORT_TEXT,
    )
    assert excluded is True
    assert "ui_form_heuristic" in reason
    assert page_type == "ui_flow_excluded"


def test_should_exclude_skips_heuristic_without_html_text() -> None:
    """should_exclude does not run heuristic when html/text omitted."""
    excluded, _, _ = should_exclude("https://example.com/info")
    assert excluded is False
