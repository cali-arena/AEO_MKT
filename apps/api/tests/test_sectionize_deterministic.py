"""Tests for sectionize determinism: same html/text => same sections."""

import pytest

from apps.api.services.sectionize import sectionize


HTML_WITH_HEADINGS = """<!DOCTYPE html>
<html><head><title>Doc</title></head>
<body>
<h1>Main Title</h1>
<p>Intro paragraph under h1.</p>
<h2>Section A</h2>
<p>Content for section A.</p>
<h2>Section B</h2>
<p>Content for section B.</p>
</body></html>"""

TEXT_PLAIN = "Paragraph one.\n\nParagraph two with more content.\n\nParagraph three."


def test_same_html_same_sections() -> None:
    """Same html and text produce same number of sections and same heading_path+section_text."""
    url = "https://example.com/page"
    text = "Main Title Intro paragraph under h1. Section A Content for section A. Section B Content for section B."
    r1 = sectionize(HTML_WITH_HEADINGS, text, url)
    r2 = sectionize(HTML_WITH_HEADINGS, text, url)
    assert len(r1) == len(r2)
    for a, b in zip(r1, r2):
        assert a["heading_path"] == b["heading_path"]
        assert a["section_text"] == b["section_text"]


def test_same_text_fallback_same_sections() -> None:
    """Same text (fallback mode) produces same sections."""
    url = "https://example.com/fallback"
    text = "A" * 3000  # triggers paragraph fallback chunking
    r1 = sectionize(None, text, url)
    r2 = sectionize(None, text, url)
    assert len(r1) == len(r2)
    for a, b in zip(r1, r2):
        assert a["heading_path"] == b["heading_path"]
        assert a["section_text"] == b["section_text"]


def test_heading_extraction_produces_expected_structure() -> None:
    """HTML with h1/h2 yields sections with heading_path."""
    url = "https://example.com/doc"
    text = "Main Title intro. Section A content A. Section B content B."
    sections = sectionize(HTML_WITH_HEADINGS, text, url)
    assert len(sections) >= 2
    paths = [s["heading_path"] for s in sections]
    assert "Main Title" in paths[0] or "Main Title" in sections[0]["section_text"]
    assert any("Section A" in p or "Section A" in s["section_text"] for p, s in [(x["heading_path"], x) for x in sections])
