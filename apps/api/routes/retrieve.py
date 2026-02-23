"""Retrieve endpoints: POST /retrieve/ac and POST /retrieve/ec.

Tenant injected server-side from auth; client-provided tenant_id ignored.
"""

from fastapi import APIRouter

from apps.api.schemas.requests import RetrieveECRequest, RetrieveRequest
from apps.api.schemas.responses import RetrieveECResponse, RetrieveResponse
from apps.api.services.retrieve import retrieve_ac as retrieve_ac_service, retrieve_ec as retrieve_ec_service
from apps.api.services.tenant_context import TenantId

router = APIRouter()


@router.post("/ac", response_model=RetrieveResponse)
async def retrieve_ac(body: RetrieveRequest, tenant_id: TenantId) -> RetrieveResponse:
    """Retrieve candidates for AC (assistant context). Section-level. Tenant from auth only."""
    return retrieve_ac_service(tenant_id, body.query, k=body.k)


@router.post("/ec", response_model=RetrieveECResponse)
async def retrieve_ec(body: RetrieveECRequest, tenant_id: TenantId) -> RetrieveECResponse:
    """Retrieve entity-level candidates for EC. Vector search + mentions. Tenant from auth only."""
    return retrieve_ec_service(tenant_id, body.query, k=body.k, n=body.n)
