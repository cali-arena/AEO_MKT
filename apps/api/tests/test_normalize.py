"""Tests for normalize module: normalize_text and content_hash."""

import pytest

from apps.api.services.normalize import content_hash, normalize_text


def test_same_input_same_normalized() -> None:
    """Same input produces same normalized output."""
    text = "Hello  world"
    a = normalize_text(text)
    b = normalize_text(text)
    assert a == b
    assert a == "Hello world"


def test_same_input_same_hash() -> None:
    """Same input produces same hash."""
    text = "Hello world"
    h1 = content_hash(text)
    h2 = content_hash(text)
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_whitespace_only_changes_same_hash() -> None:
    """Whitespace-only changes (spaces, tabs, line endings) produce same hash when equivalent."""
    # Extra spaces / tabs collapse to single space
    a = "foo bar baz"
    b = "  foo   bar   baz  "
    c = "foo\tbar\tbaz"
    assert content_hash(a) == content_hash(b) == content_hash(c)

    # CRLF vs LF normalize to same
    d = "foo\nbar\nbaz"
    e = "foo\r\nbar\r\nbaz"
    assert content_hash(d) == content_hash(e)

    # Multiple newlines collapse to max 2
    f = "a\n\n\nb"
    g = "a\n\nb"
    assert content_hash(f) == content_hash(g)


def test_whitespace_normalization_details() -> None:
    """Verify normalize_text rules."""
    assert normalize_text("  a  b  ") == "a b"
    assert normalize_text("a\r\nb") == "a\nb"
    assert normalize_text("a\n\n\nb") == "a\n\nb"
    assert normalize_text("a\t\t  b") == "a b"
    assert normalize_text("  line1  \n  line2  ") == "line1\nline2"


def test_real_content_change_different_hash() -> None:
    """Real content change produces different hash."""
    h1 = content_hash("foo bar")
    h2 = content_hash("foo baz")
    h3 = content_hash("Foo bar")
    assert h1 != h2
    assert h1 != h3
    assert h2 != h3
