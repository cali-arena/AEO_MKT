"""Tests for page type inference."""

import pytest

from apps.api.services.page_type import infer_page_type


def test_faq_by_path() -> None:
    assert infer_page_type("https://example.com/faq") == "faq"
    assert infer_page_type("https://example.com/support/faq") == "faq"


def test_faq_by_title() -> None:
    assert infer_page_type("https://example.com/help", title="FAQ - Common Questions") == "faq"


def test_service_by_path() -> None:
    assert infer_page_type("https://example.com/services") == "service"
    assert infer_page_type("https://example.com/services/moving") == "service"


def test_service_by_title() -> None:
    assert infer_page_type("https://example.com/", title="Our Services") == "service"


def test_blog_by_path() -> None:
    assert infer_page_type("https://example.com/blog") == "blog"
    assert infer_page_type("https://example.com/blog/post-slug") == "blog"


def test_blog_by_title() -> None:
    assert infer_page_type("https://example.com/news", title="Company Blog") == "blog"


def test_blog_dated_article() -> None:
    assert infer_page_type("https://example.com/2024/01/my-post") == "blog"
    assert infer_page_type("https://example.com/blog/2024-01-15-title") == "blog"


def test_informational_long_text_with_keywords() -> None:
    text = "A" * 900 + " about our company mission and locations "
    assert infer_page_type("https://example.com/page", text=text) == "informational"


def test_informational_short_text_not_triggered() -> None:
    text = "about company mission"  # < 800 chars
    assert infer_page_type("https://example.com/page", text=text) == "unknown"


def test_unknown() -> None:
    assert infer_page_type("https://example.com/other") == "unknown"
    assert infer_page_type("https://example.com/") == "unknown"
