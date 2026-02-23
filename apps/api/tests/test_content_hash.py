"""Tests for content hashing (normalize.content_hash)."""

import pytest

from apps.api.services.normalize import content_hash


def test_same_input_same_hash() -> None:
    """Same input produces same hash."""
    text = "Hello world"
    h1 = content_hash(text)
    h2 = content_hash(text)
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_different_input_different_hash() -> None:
    """Different input produces different hash."""
    h1 = content_hash("foo")
    h2 = content_hash("bar")
    assert h1 != h2
