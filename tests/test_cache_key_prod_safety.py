"""Cache key production safety: make_cache_key 5-part format, build_cache_key test-only."""

from unittest.mock import patch

import pytest

from apps.api.services.cache import build_cache_key, make_cache_key


def test_make_cache_key_produces_five_part_format() -> None:
    """make_cache_key returns key with exactly 5 colon-separated parts including crawl_policy_version."""
    key = make_cache_key(
        tenant_id="t1",
        query_hash="qh_abc",
        ac_version_hash="ac_v1",
        ec_version_hash="ec_v1",
        crawl_policy_version="crawl_v2",
    )
    parts = key.split(":")
    assert len(parts) == 5, f"Expected 5 parts, got {len(parts)}: {parts}"
    assert parts[0] == "t1"
    assert parts[1] == "qh_abc"
    assert parts[2] == "ac_v1"
    assert parts[3] == "ec_v1"
    assert parts[4] == "crawl_v2", "5th part must be crawl_policy_version"


def test_build_cache_key_raises_outside_test_env() -> None:
    """When ENV != 'test', build_cache_key raises RuntimeError."""
    with pytest.raises(RuntimeError, match="deprecated|test-only"):
        with patch.dict("os.environ", {"ENV": "production"}, clear=False):
            build_cache_key("t", "qh", "ac", "ec")
