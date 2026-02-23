"""Auth middleware: inject tenant_id from Authorization header only.
Tenant comes from Bearer tenant:<id> or JWT tenant_id claim (when JWT support enabled).
Client-provided tenant_id in query/body/headers is explicitly ignored, except X-Tenant-Debug
when ENV=test AND ENABLE_TEST_TENANT_HEADER=1 (testing only)."""

import os
import re
from typing import Literal

from starlette.requests import Request
from starlette.responses import JSONResponse

# "Bearer tenant:A" or "Bearer tenant=B"
BEARER_TENANT_PATTERN = re.compile(r"^Bearer\s+tenant[:=](.+)$", re.IGNORECASE)


def _is_production() -> bool:
    """Return True if environment indicates production."""
    env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower()
    return env in ("production", "prod")


def _allow_tenant_debug_header() -> bool:
    """Only allow X-Tenant-Debug when ENV=test AND ENABLE_TEST_TENANT_HEADER=1. Otherwise ignored (tenant never from client)."""
    if _is_production():
        return False
    env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower()
    if env != "test":
        return False
    return os.getenv("ENABLE_TEST_TENANT_HEADER", "").lower() in ("1", "true", "yes")


def _parse_tenant_from_jwt(token: str) -> tuple[str | None, str | None]:
    """Try to decode JWT and read tenant_id (and sub as actor_id). Returns (tenant_id, actor_id) or (None, None).
    Requires PyJWT. Unverified decode for now; add signature verification for production."""
    try:
        import jwt as pyjwt
    except ImportError:
        return None, None
    try:
        payload = pyjwt.decode(token, options={"verify_signature": False})
        tid = payload.get("tenant_id")
        aid = payload.get("sub")
        return (str(tid).strip(), str(aid).strip() if aid else None) if tid else (None, None)
    except Exception:
        return None, None


def _parse_tenant_from_debug_header(request: Request) -> str | None:
    """Parse tenant_id from X-Tenant-Debug header. Returns None if disabled or missing. Ignored when not allowed."""
    if not _allow_tenant_debug_header():
        return None
    val = request.headers.get("X-Tenant-Debug")
    if not val:
        return None
    return val.strip() or None


def _extract_tenant_and_actor(auth_header: str) -> tuple[str | Literal[False], str | None]:
    """Parse tenant_id and optional actor_id from Bearer token. Returns (tenant_id, actor_id)."""
    if not auth_header or not auth_header.strip().lower().startswith("bearer "):
        return False, None
    token = auth_header.strip()[7:].strip()
    m = BEARER_TENANT_PATTERN.match(auth_header.strip())
    if m:
        return m.group(1).strip() or False, None
    tid, aid = _parse_tenant_from_jwt(token)
    return (tid if tid else False, aid)


async def auth_middleware(request: Request, call_next):
    """Extract tenant_id from Authorization header. X-Tenant-Debug allowed only when ENV=test and ENABLE_TEST_TENANT_HEADER=1.
    Never reads tenant_id from query params or body. /health is exempt (no auth required)."""

    if request.url.path.rstrip("/") == "/health":
        return await call_next(request)

    tenant_id: str | None | Literal[False] = None
    actor_id: str | None = None

    auth_header = request.headers.get("Authorization")
    if auth_header:
        parsed, actor_id = _extract_tenant_and_actor(auth_header)
        if parsed is not False:
            tenant_id = parsed

    if tenant_id is None:
        tenant_id = _parse_tenant_from_debug_header(request)

    if not tenant_id or not str(tenant_id).strip():
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid tenant. Use Authorization: Bearer tenant:A or JWT with tenant_id claim"},
        )

    request.state.tenant_id = str(tenant_id).strip()
    if actor_id:
        request.state.actor_id = actor_id
    return await call_next(request)
