"""Unit tests for cache key format."""

from unittest.mock import patch

import pytest

from apps.api.services.cache import build_cache_key
from apps.api.services.repo import TenantRequiredError


def test_build_cache_key_format() -> None:
    """Key format is tenant_id:query_hash:ac_version_hash:ec_version_hash."""
    key = build_cache_key(
        tenant_id="t1",
        query_hash="qh_abc",
        ac_version_hash="ac_v1",
        ec_version_hash="ec_v1",
    )
    assert key == "t1:qh_abc:ac_v1:ec_v1"


def test_build_cache_key_preserves_all_components() -> None:
    """All four components appear in order with colons."""
    tenant_id = "tenant-123"
    query_hash = "sha256:deadbeef"
    ac_version_hash = "ac_xyz"
    ec_version_hash = "ec_xyz"
    key = build_cache_key(tenant_id, query_hash, ac_version_hash, ec_version_hash)
    parts = key.split(":")
    assert len(parts) >= 4
    assert parts[0] == tenant_id
    assert query_hash in key
    assert ac_version_hash in key
    assert ec_version_hash in key


def test_build_cache_key_raises_on_empty_tenant_id() -> None:
    """Raises TenantRequiredError when tenant_id is empty."""
    with pytest.raises(TenantRequiredError):
        build_cache_key("", "qh", "ac", "ec")


def test_build_cache_key_raises_on_whitespace_tenant_id() -> None:
    """Raises TenantRequiredError when tenant_id is whitespace only."""
    with pytest.raises(TenantRequiredError):
        build_cache_key("   ", "qh", "ac", "ec")


def test_build_cache_key_raises_on_none_tenant_id() -> None:
    """Raises TenantRequiredError when tenant_id is None."""
    with pytest.raises(TenantRequiredError):
        build_cache_key(None, "qh", "ac", "ec")


def test_build_cache_key_accepts_hash_like_values() -> None:
    """query_hash, ac_version_hash, ec_version_hash can contain colons."""
    key = build_cache_key("t", "a:b:c", "x:y", "p:q:r:s")
    assert key == "t:a:b:c:x:y:p:q:r:s"


def test_build_cache_key_raises_when_env_not_test() -> None:
    """build_cache_key is test-only; raises RuntimeError when ENV != 'test'."""
    with pytest.raises(RuntimeError, match="deprecated.*make_cache_key"):
        with patch.dict("os.environ", {"ENV": "production"}, clear=False):
            build_cache_key("t", "qh", "ac", "ec")
