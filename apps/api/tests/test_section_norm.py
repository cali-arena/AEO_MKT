"""Tests for section_norm: normalize_for_id and sha256_hex."""

import pytest

from apps.api.services.section_norm import normalize_for_id, sha256_hex


def test_whitespace_differences_normalize_to_same() -> None:
    """Whitespace-only differences produce same normalized output."""
    a = "foo bar baz"
    b = "  foo   bar   baz  "
    c = "foo\tbar\tbaz"
    assert normalize_for_id(a) == normalize_for_id(b) == normalize_for_id(c) == "foo bar baz"

    d = "foo\nbar\nbaz"
    e = "foo\r\nbar\r\nbaz"
    assert normalize_for_id(d) == normalize_for_id(e) == "foo\nbar\nbaz"

    f = "  line1  \n  line2  "
    assert normalize_for_id(f) == "line1\nline2"


def test_hash_stable_across_runs() -> None:
    """Hash is stable across runs."""
    text = "Hello world"
    h1 = sha256_hex(normalize_for_id(text))
    h2 = sha256_hex(normalize_for_id(text))
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_sha256_hex_deterministic() -> None:
    """sha256_hex produces same output for same input."""
    s = "test"
    assert sha256_hex(s) == sha256_hex(s)
