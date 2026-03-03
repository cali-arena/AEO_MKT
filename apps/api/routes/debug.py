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


# Admin/debug: per-domain index stats (strict tenant_id + domain counts).
# Mount with prefix="/tenants" so path is /tenants/{tenant_id}/domains/{domain}/debug/index-stats
index_stats_router = APIRouter()


@index_stats_router.get("/{tenant_id}/domains/{domain}/debug/index-stats")
async def get_domain_index_stats(tenant_id: str, domain: str) -> dict:
    """
    Return raw_pages, sections, ac_embeddings, ec_embeddings and index_state for (tenant_id, domain).
    Temporary admin/debug endpoint. All counts are domain-scoped (no global counts).
    """
    from apps.api.services.domain_index_validation import get_domain_index_stats as get_stats

    return get_stats(tenant_id, domain)
