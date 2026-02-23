"""Tests for span extraction."""

import pytest

from apps.api.services.span import select_quote_span


def test_quote_span_equals_slice() -> None:
    """quote_span must equal section_text[start_char:end_char]."""
    section_text = "First sentence. Second sentence with keywords. Third sentence."
    quote_span, start_char, end_char = select_quote_span(section_text, "keywords second")
    assert quote_span == section_text[start_char:end_char]


def test_offsets_valid() -> None:
    """start_char and end_char must be valid indices."""
    section_text = "Hello world. Foo bar. Baz qux."
    quote_span, start_char, end_char = select_quote_span(section_text, "foo")
    assert 0 <= start_char <= end_char <= len(section_text)
    assert quote_span == section_text[start_char:end_char]


def test_empty_section() -> None:
    """Empty section returns empty span and zero offsets."""
    quote_span, start_char, end_char = select_quote_span("", "query")
    assert quote_span == ""
    assert start_char == 0
    assert end_char == 0


def test_best_sentence_selected_by_overlap() -> None:
    """Sentence with most query token overlap is selected."""
    section_text = "Alpha beta. Gamma delta epsilon. Zeta eta theta."
    quote_span, start_char, end_char = select_quote_span(section_text, "gamma delta")
    assert "Gamma delta" in quote_span
    assert quote_span == section_text[start_char:end_char]


def test_fallback_to_first_sentence_when_no_overlap() -> None:
    """When no overlap, first sentence is used."""
    section_text = "First sentence here. Second sentence. Third."
    quote_span, start_char, end_char = select_quote_span(section_text, "nonexistent word xyz")
    assert "First sentence" in quote_span
    assert quote_span == section_text[start_char:end_char]


def test_trim_when_over_max_len() -> None:
    """Long sentence is trimmed to max_len, offsets still valid."""
    long_sentence = "A" * 200 + " keyword " + "B" * 200
    section_text = "Short. " + long_sentence + "."
    quote_span, start_char, end_char = select_quote_span(section_text, "keyword", max_len=50)
    assert len(quote_span) <= 50
    assert 0 <= start_char <= end_char <= len(section_text)
    assert quote_span == section_text[start_char:end_char]
