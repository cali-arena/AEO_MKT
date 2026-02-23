"""Unit tests for sectionizer stability and version hashing."""

import pytest

from apps.api.services.sectionize import compute_section_ids, compute_section_metadata


def test_same_url_same_chunking_same_section_ids() -> None:
    """Same URL + same chunking => same section_ids."""
    url = "https://example.com/page"
    text = "x" * 2500
    ids1 = compute_section_ids(url, text)
    ids2 = compute_section_ids(url, text)
    assert ids1 == ids2


def test_same_input_same_section_ids() -> None:
    """Same input text produces same section_ids (deterministic)."""
    url = "https://example.com/page"
    text = "x" * 2500
    ids1 = compute_section_ids(url, text)
    ids2 = compute_section_ids(url, text)
    assert ids1 == ids2


def test_chunk_text_changes_same_index_section_id_same_version_hash_changes() -> None:
    """If chunk text changes but chunk index same => section_id same but version_hash changes."""
    url = "https://example.com/doc"
    text1 = "a" * 500
    text2 = "b" * 500
    meta1 = compute_section_metadata(url, text1)
    meta2 = compute_section_metadata(url, text2)
    assert len(meta1) == 1 and len(meta2) == 1
    assert meta1[0]["section_id"] == meta2[0]["section_id"], "section_id must be stable by URL + index"
    assert meta1[0]["version_hash"] != meta2[0]["version_hash"], "version_hash must change when text changes"


def test_different_url_different_section_ids() -> None:
    """Different URL produces different section_ids for same text."""
    text = "x" * 1100
    ids1 = compute_section_ids("https://a.com/p", text)
    ids2 = compute_section_ids("https://b.com/p", text)
    assert ids1 != ids2


def test_section_id_format() -> None:
    """section_ids start with sec_ and are 20 chars."""
    ids = compute_section_ids("https://x.com", "short")
    assert len(ids) == 1
    assert ids[0].startswith("sec_")
    assert len(ids[0]) == 20


def test_chunking_produces_overlapping_sections() -> None:
    """Long text produces multiple sections with overlap."""
    text = "a" * 2500
    ids = compute_section_ids("https://x.com", text)
    assert len(ids) >= 2
    assert len(set(ids)) == len(ids)
