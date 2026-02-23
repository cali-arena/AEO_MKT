"""Lightweight debug endpoints for testing. Enabled only when ENV=test.

No embeddings, retrieval, or DB; used by auth tests to verify tenant injection
without triggering heavy code paths.
"""

from fastapi import APIRouter

from apps.api.services.tenant_context import TenantId

router = APIRouter()


@router.get("/tenant")
async def debug_tenant(tenant_id: TenantId) -> dict:
    """Return tenant_id from auth. Requires auth. For testing only (ENV=test)."""
    return {"tenant_id": tenant_id}
