"""Server-side tenant context injection.

Tenant is taken from auth (Authorization header: Bearer tenant:<id> or JWT tenant_id claim).
Client-provided tenant_id in query/body is explicitly ignored.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

# Keys that MUST NOT be trusted from query/body; tenant comes from auth only
IGNORED_CLIENT_TENANT_KEYS = frozenset({"tenant_id", "tenant", "x-tenant-id"})


def tenant_guard(tenant_id: str | None) -> str:
    """Assert tenant_id is present and non-empty before any DB query.
    Returns stripped tenant_id. Raises ValueError if invalid."""
    if not tenant_id or not str(tenant_id).strip():
        raise ValueError("tenant_id is required and must be non-empty")
    return str(tenant_id).strip()


@dataclass(frozen=True)
class TenantContext:
    """Tenant context from auth. tenant_id required; actor_id optional (e.g. from JWT sub)."""

    tenant_id: str
    actor_id: str | None = None


def get_tenant_id(request: Request) -> str:
    """FastAPI dependency: return tenant_id from request.state (set by auth middleware).
    Raises 401 if missing. Client-provided tenant_id in query/body is ignored."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id or not str(tenant_id).strip():
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Tenant ID required")
    return str(tenant_id).strip()


def get_tenant_context(request: Request) -> TenantContext:
    """FastAPI dependency: return TenantContext from request.state."""
    tenant_id = get_tenant_id(request)
    actor_id = getattr(request.state, "actor_id", None)
    return TenantContext(tenant_id=tenant_id, actor_id=actor_id)


# Type aliases for Depends()
TenantId = Annotated[str, Depends(get_tenant_id)]
TenantContextDep = Annotated[TenantContext, Depends(get_tenant_context)]
