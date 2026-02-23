"""Tests for policy version determinism and sensitivity."""

import pytest

from apps.api.services.policy import canonical_json, crawl_policy_version, load_policy


def test_load_policy_twice_same_version() -> None:
    """Load policy twice -> same version."""
    p1 = load_policy()
    p2 = load_policy()
    v1 = crawl_policy_version(p1)
    v2 = crawl_policy_version(p2)
    assert v1 == v2


def test_modify_policy_version_changes() -> None:
    """Modify one field in-memory -> version changes."""
    policy = load_policy()
    v_orig = crawl_policy_version(policy)

    modified = dict(policy)
    modified["allowed_domains"] = list(policy["allowed_domains"]) + ["newdomain.com"]
    v_modified = crawl_policy_version(modified)
    assert v_modified != v_orig


def test_canonical_json_deterministic() -> None:
    """canonical_json produces same output for same object."""
    obj = {"b": 2, "a": 1}
    assert canonical_json(obj) == canonical_json(obj)
    assert canonical_json(obj) == '{"a":1,"b":2}'
