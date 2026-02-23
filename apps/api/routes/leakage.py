"""Leakage endpoints. Alias for /leakage/latest (spec); /monitor/leakage/latest also available."""

from fastapi import APIRouter

from apps.api.routes.monitor import get_leakage_latest_response
from apps.api.schemas.monitor_read import LeakageLatestResponse
from apps.api.services.tenant_context import TenantId

router = APIRouter()


@router.get("/leakage/latest", response_model=LeakageLatestResponse)
async def get_leakage_latest(tenant_id: TenantId) -> LeakageLatestResponse:
    """Return latest leakage status. Tenant inferred from auth. Alias for /monitor/leakage/latest."""
    return get_leakage_latest_response(tenant_id)
