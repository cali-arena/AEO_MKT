"""Unit tests for cache key format and normalize_query."""

import pytest

from apps.api.services.cache import (
    compute_query_hash,
    make_cache_key,
    normalize_query,
)


def test_normalize_query_trim_collapse_lowercase() -> None:
    """normalize_query trims, collapses spaces, lowercases."""
    assert normalize_query("  Hello   World  ") == "hello world"
    assert normalize_query("FOO") == "foo"
    assert normalize_query("") == ""
    assert normalize_query("   ") == ""


def test_normalize_query_collapse_multiple_spaces() -> None:
    """Multiple spaces collapse to single space."""
    assert normalize_query("a   b\tc\n  d") == "a b c d"


def test_compute_query_hash_hex16() -> None:
    """query_hash is first 16 chars of sha256 hex."""
    h = compute_query_hash("hello")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)
    assert compute_query_hash("hello") == compute_query_hash("hello")
    assert compute_query_hash("hello") != compute_query_hash("world")


def test_make_cache_key_format() -> None:
    """make_cache_key produces tenant_id:query_hash:ac:ec:crawl_policy_version."""
    key = make_cache_key("t1", "abc123", "ac1", "ec1", "crawl1")
    assert key == "t1:abc123:ac1:ec1:crawl1"


def test_make_cache_key_empty_components() -> None:
    """Empty string components are allowed (e.g. missing versions)."""
    key = make_cache_key("t", "qh", "", "", "")
    assert key == "t:qh:::"


def test_make_cache_key_deterministic() -> None:
    """Same inputs produce same key."""
    k1 = make_cache_key("tenant_a", "deadbeef12345678", "acv", "ecv", "cpv")
    k2 = make_cache_key("tenant_a", "deadbeef12345678", "acv", "ecv", "cpv")
    assert k1 == k2


def test_full_flow_normalize_query_hash_key() -> None:
    """End-to-end: normalize -> hash -> key."""
    q = "  What is moving?  "
    norm = normalize_query(q)
    assert norm == "what is moving?"
    qh = compute_query_hash(norm)
    assert len(qh) == 16
    key = make_cache_key("tenant_1", qh, "ac_v1", "ec_v1", "crawl_v1")
    assert key.startswith("tenant_1:")
    assert qh in key
    assert "ac_v1" in key
    assert "ec_v1" in key
    assert "crawl_v1" in key
