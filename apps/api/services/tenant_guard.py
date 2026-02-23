"""Tenant-scoped query choke point. All repo methods must use require_tenant_id and tenant_where."""

from apps.api.repositories.tenant_filters import tenant_where


class TenantRequiredError(ValueError):
    """Raised when tenant_id is None or empty."""

    pass


def require_tenant_id(tenant_id: str | None) -> str:
    """
    Validate tenant_id; return stripped value. Raises TenantRequiredError if missing/empty.
    Call at start of every tenant-scoped repo method.
    """
    if not tenant_id or not str(tenant_id).strip():
        raise TenantRequiredError("tenant_id is required and must be non-empty")
    return str(tenant_id).strip()


__all__ = ["TenantRequiredError", "require_tenant_id", "tenant_where"]
