"""Unit tests for exclusion URL rules."""

import pytest

from apps.api.services.exclusion import should_exclude


def test_path_prefix_excluded() -> None:
    """Path starting with deny prefix is excluded."""
    excluded, reason, page_type = should_exclude("https://example.com/get-quote")
    assert excluded is True
    assert reason == "deny_path_prefix:/get-quote"
    assert page_type == "ui_flow_excluded"


def test_path_prefix_quote() -> None:
    excluded, reason, _ = should_exclude("https://example.com/quote/start")
    assert excluded is True
    assert reason == "deny_path_prefix:/quote"


def test_path_contains_step_excluded() -> None:
    """Path containing step pattern is excluded."""
    excluded, reason, page_type = should_exclude("https://example.com/about/step-1")
    assert excluded is True
    assert reason == "deny_path_contains:step-1"
    assert page_type == "ui_flow_excluded"


def test_query_key_excluded() -> None:
    """Query containing deny key is excluded."""
    excluded, reason, _ = should_exclude("https://example.com/page?session=abc")
    assert excluded is True
    assert reason == "deny_query_key:session"


def test_query_key_step_excluded() -> None:
    """Query key step is excluded (lowercase handling)."""
    excluded, reason, _ = should_exclude("https://quote.unitedglobalvanline.com/estimate?step=1")
    assert excluded is True
    assert "step" in reason or "estimate" in reason
    excluded2, reason2, _ = should_exclude("https://example.com/page?Step=2")
    assert excluded2 is True
    assert reason2 == "deny_query_key:step"


def test_query_prefix_utm_excluded() -> None:
    """Query key starting with utm_ is excluded."""
    excluded, reason, _ = should_exclude("https://example.com/page?utm_source=google")
    assert excluded is True
    assert reason == "deny_query_prefix:utm_source"


def test_allowed_url() -> None:
    """Clean URL is allowed."""
    excluded, reason, page_type = should_exclude("https://example.com/about")
    assert excluded is False
    assert reason == ""
    assert page_type == "info_static"


def test_html_text_unused() -> None:
    """html and text params are accepted but do not affect result."""
    excluded1, _, _ = should_exclude("https://example.com/about")
    excluded2, _, _ = should_exclude("https://example.com/about", html="<html></html>", text="Hello")
    assert excluded1 == excluded2 is False
