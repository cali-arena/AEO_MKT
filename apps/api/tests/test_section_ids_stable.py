"""Tests for stable section_id, section_hash, version_hash."""

import pytest

from apps.api.services.sectionize import _build_section_records, sectionize


def test_same_content_same_section_id() -> None:
    """Same content => same section_id."""
    url = "https://example.com/doc"
    sections = [{"heading_path": "Main", "section_text": "Hello world content."}]
    r1 = _build_section_records(sections, url, 1)
    r2 = _build_section_records(sections, url, 1)
    assert len(r1) == 1 and len(r2) == 1
    assert r1[0]["section_id"] == r2[0]["section_id"]
    assert r1[0]["section_hash"] == r2[0]["section_hash"]
    assert r1[0]["version_hash"] == r2[0]["version_hash"]


def test_text_change_section_hash_and_version_hash_change() -> None:
    """Text change => section_hash changes and version_hash changes."""
    url = "https://example.com/doc"
    sec1 = [{"heading_path": "A", "section_text": "Original content."}]
    sec2 = [{"heading_path": "A", "section_text": "Modified content."}]
    r1 = _build_section_records(sec1, url, 1)
    r2 = _build_section_records(sec2, url, 1)
    assert r1[0]["section_id"] != r2[0]["section_id"]
    assert r1[0]["section_hash"] != r2[0]["section_hash"]
    assert r1[0]["version_hash"] != r2[0]["version_hash"]


def test_raw_page_version_increments_version_hash_changes() -> None:
    """Same section text, different raw_page.version => version_hash changes."""
    url = "https://example.com/doc"
    sections = [{"heading_path": "A", "section_text": "Same content."}]
    r1 = _build_section_records(sections, url, 1)
    r2 = _build_section_records(sections, url, 2)
    assert r1[0]["section_id"] == r2[0]["section_id"]
    assert r1[0]["section_hash"] == r2[0]["section_hash"]
    assert r1[0]["version_hash"] != r2[0]["version_hash"]


def test_same_content_via_sectionize_same_section_id() -> None:
    """Same html/text via sectionize => same section_ids."""
    url = "https://example.com/page"
    html = "<html><body><h1>Title</h1><p>Body text.</p></body></html>"
    text = "Title Body text."
    content_hash = "xyz"
    s1 = sectionize(html, text, url)
    s2 = sectionize(html, text, url)
    r1 = _build_section_records(s1, url, content_hash)
    r2 = _build_section_records(s2, url, content_hash)
    assert len(r1) == len(r2)
    for a, b in zip(r1, r2):
        assert a["section_id"] == b["section_id"]
        assert a["section_hash"] == b["section_hash"]
