"""Tests for auth middleware: tenant injection from Authorization header.

Uses /debug/tenant (ENV=test only) to avoid embeddings/retrieval/DB.
"""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_auth_with_bearer_tenant_injects_tenant_id() -> None:
    """Call /debug/tenant with Authorization: Bearer tenant:<id> and assert tenant_id matches."""
    resp = client.get("/debug/tenant", headers={"Authorization": "Bearer tenant:my-tenant-123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == "my-tenant-123"


def test_auth_without_header_returns_401() -> None:
    """Call /debug/tenant without Authorization and assert 401."""
    resp = client.get("/debug/tenant")
    assert resp.status_code == 401


def test_auth_invalid_bearer_returns_401() -> None:
    """Call /debug/tenant with invalid Authorization format and assert 401."""
    resp = client.get(
        "/debug/tenant",
        headers={"Authorization": "Bearer invalid"},
    )
    assert resp.status_code == 401


def test_auth_tenant_from_bearer_not_header_when_debug_disabled() -> None:
    """When both Bearer and X-Tenant-Debug present, tenant comes from Bearer (header ignored unless ENV=test + ENABLE_TEST_TENANT_HEADER)."""
    resp = client.get(
        "/debug/tenant",
        headers={
            "Authorization": "Bearer tenant:bearer-tenant-id",
            "X-Tenant-Debug": "header-tenant-id",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == "bearer-tenant-id"


def test_x_tenant_debug_ignored_in_non_test_env(monkeypatch) -> None:
    """In non-test env, X-Tenant-Debug has no effect; tenant must come from Bearer token."""
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("ENABLE_TEST_TENANT_HEADER", "1")

    # Header alone (no Bearer) must be ignored -> 401
    resp = client.get("/debug/tenant", headers={"X-Tenant-Debug": "debug-tenant-id"})
    assert resp.status_code == 401

    # Bearer still works
    resp2 = client.get("/debug/tenant", headers={"Authorization": "Bearer tenant:valid-tenant"})
    assert resp2.status_code == 200
    assert resp2.json()["tenant_id"] == "valid-tenant"


def test_x_tenant_debug_allowed_only_when_test_env_and_flag(monkeypatch) -> None:
    """X-Tenant-Debug injects tenant only when ENV=test AND ENABLE_TEST_TENANT_HEADER=1."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("ENABLE_TEST_TENANT_HEADER", "1")

    resp = client.get("/debug/tenant", headers={"X-Tenant-Debug": "debug-only-tenant"})
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "debug-only-tenant"
