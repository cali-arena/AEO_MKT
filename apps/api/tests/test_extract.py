"""Tests for extract module: extract_main_text and extract_title."""

from pathlib import Path

import pytest

from apps.api.services.extract import extract_main_text, extract_title

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

# Minimal HTML - trafilatura often returns None/empty for non-article markup; triggers BS4 fallback
HTML_MINIMAL = """<!DOCTYPE html>
<html><head><title>Minimal Title</title></head>
<body><p>Hello world</p><script>x=1</script></body></html>"""

# Article-like HTML - trafilatura can extract
HTML_ARTICLE = """<!DOCTYPE html>
<html><head><title>Article Title</title></head>
<body>
<article>
<h1>Main Heading</h1>
<p>First paragraph with meaningful content.</p>
<p>Second paragraph for the body.</p>
</article>
</body></html>"""

# No title tag
HTML_NO_TITLE = "<html><body><p>Content only</p></body></html>"


def test_extract_main_text_returns_non_empty() -> None:
    """extract_main_text returns non-empty string for valid HTML."""
    text = extract_main_text(HTML_MINIMAL)
    assert isinstance(text, str)
    assert len(text) > 0
    assert "Hello world" in text
    assert "x=1" not in text  # script removed


def test_extract_main_text_article() -> None:
    """extract_main_text extracts article body (trafilatura or fallback)."""
    text = extract_main_text(HTML_ARTICLE)
    assert "meaningful content" in text or "First paragraph" in text
    assert "Main Heading" in text or "First paragraph" in text


def test_extract_main_text_deterministic() -> None:
    """Same HTML produces same result."""
    a = extract_main_text(HTML_MINIMAL)
    b = extract_main_text(HTML_MINIMAL)
    assert a == b


def test_extract_main_text_empty_fallback() -> None:
    """Empty/minimal HTML returns empty string from fallback, not None."""
    text = extract_main_text("<html><body></body></html>")
    assert isinstance(text, str)
    assert text == "" or text.strip() == ""


def test_extract_title_present() -> None:
    """extract_title returns title text when present."""
    assert extract_title(HTML_MINIMAL) == "Minimal Title"
    assert extract_title(HTML_ARTICLE) == "Article Title"


def test_extract_title_absent() -> None:
    """extract_title returns None when no title tag."""
    assert extract_title(HTML_NO_TITLE) is None


def test_extract_title_deterministic() -> None:
    """Same HTML produces same title."""
    assert extract_title(HTML_MINIMAL) == extract_title(HTML_MINIMAL)


def test_extract_from_fixture_file() -> None:
    """Extract from sample.html fixture."""
    path = FIXTURE_DIR / "sample.html"
    if not path.exists():
        pytest.skip("fixture sample.html not found")
    html = path.read_text(encoding="utf-8")
    text = extract_main_text(html)
    title = extract_title(html)
    assert "main body content" in text or "informational text" in text
    assert title == "Sample Page Title"
