"""Tenant helper utilities. Prefer tenant_context.get_tenant_id for FastAPI Depends."""

from fastapi import HTTPException
from starlette.requests import Request


def require_tenant_id(request: Request) -> str:
    """Return tenant_id from request state. Raises HTTPException(401) if missing or empty."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id or not str(tenant_id).strip():
        raise HTTPException(status_code=401, detail="Tenant ID required")
    return str(tenant_id).strip()


def get_tenant_id(request: Request) -> str:
    """Get tenant_id from request state (injected by auth middleware). Returns empty string if missing."""
    return getattr(request.state, "tenant_id", "")
