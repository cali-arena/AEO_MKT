"""Read-only monitor dashboard endpoints. Tenant from auth middleware only."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Query

from apps.api.schemas.eval import MonitorEventOut
from apps.api.schemas.monitor_read import LeakageLatestResponse
from apps.api.services.repo import list_monitor_events
from apps.api.services.tenant_context import TenantId

router = APIRouter()


def get_leakage_latest_response(tenant_id: str) -> LeakageLatestResponse:
    """Shared logic: latest leakage status from pass/fail monitor events.
    Compares last leakage_pass vs last leakage_fail; returns LeakageLatestResponse."""
    pass_events = list_monitor_events(
        tenant_id,
        event_type="leakage_pass",
        limit=1,
        offset=0,
    )
    fail_events = list_monitor_events(
        tenant_id,
        event_type="leakage_fail",
        limit=1,
        offset=0,
    )
    latest_pass = pass_events[0] if pass_events else None
    latest_fail = fail_events[0] if fail_events else None

    if latest_fail and (
        latest_pass is None or latest_pass.created_at < latest_fail.created_at
    ):
        return LeakageLatestResponse(
            tenant_id=tenant_id,
            ok=False,
            last_checked_at=latest_fail.created_at.isoformat(),
            details_json=latest_fail.details_json,
        )
    if latest_pass:
        return LeakageLatestResponse(
            tenant_id=tenant_id,
            ok=True,
            last_checked_at=latest_pass.created_at.isoformat(),
            details_json=latest_pass.details_json,
        )
    return LeakageLatestResponse(
        tenant_id=tenant_id,
        ok=True,
        last_checked_at=datetime.now(timezone.utc).isoformat(),
        details_json=None,
    )


@router.get("/leakage/latest", response_model=LeakageLatestResponse)
async def get_leakage_latest(tenant_id: TenantId) -> LeakageLatestResponse:
    """Return latest leakage status. Tenant inferred from auth.

    Compares last leakage_pass vs last leakage_fail:
    - If leakage_fail exists and (no pass or pass is older): ok=false, details from fail.
    - Else if leakage_pass exists: ok=true, last_checked_at from pass.
    - Else (no events): ok=true, last_checked_at=now.
    """
    return get_leakage_latest_response(tenant_id)


@router.get("/events", response_model=list[MonitorEventOut])
async def list_events(
    tenant_id: TenantId,
    from_: date | None = Query(None, alias="from", description="Start date (inclusive)"),
    to: date | None = Query(None, description="End date (inclusive)"),
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[MonitorEventOut]:
    """List monitor events for tenant. Ordered by created_at desc."""
    events = list_monitor_events(
        tenant_id,
        date_from=from_,
        date_to=to,
        event_type=event_type,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return [MonitorEventOut.model_validate(e) for e in events]
