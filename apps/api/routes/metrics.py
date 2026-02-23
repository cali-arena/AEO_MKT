"""Metrics dashboard endpoints. Tenant from auth middleware only."""

from fastapi import APIRouter, HTTPException, Query

from apps.api.schemas.metrics import MetricsKPIs, MetricsLatestResponse, MetricsTrendPoint, MetricsTrendsResponse
from apps.api.services.repo import aggregate_kpis_for_run, get_latest_eval_run, get_trends
from apps.api.services.tenant_context import TenantId

router = APIRouter()


@router.get("/latest", response_model=MetricsLatestResponse)
async def get_metrics_latest(tenant_id: TenantId) -> MetricsLatestResponse:
    """Fetch latest eval_run for tenant, compute KPIs, return MetricsLatestResponse.
    Tenant from auth only. 404 if no runs exist."""
    run = get_latest_eval_run(tenant_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No eval runs found for tenant",
        )
    kpis_dict = aggregate_kpis_for_run(tenant_id, run.id)
    kpis = MetricsKPIs(
        mention_rate=kpis_dict["mention_rate"],
        citation_rate=kpis_dict["citation_rate"],
        attribution_accuracy=kpis_dict["attribution_accuracy"],
        hallucinations=float(kpis_dict["hallucinations"]),
        composite_index=kpis_dict["composite_index"],
    )
    return MetricsLatestResponse(
        tenant_id=tenant_id,
        run_id=run.id,
        created_at=run.created_at,
        crawl_policy_version=run.crawl_policy_version,
        ac_version_hash=run.ac_version_hash,
        ec_version_hash=run.ec_version_hash,
        kpis=kpis,
    )


@router.get("/trends", response_model=MetricsTrendsResponse)
async def get_metrics_trends(
    tenant_id: TenantId,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
) -> MetricsTrendsResponse:
    """Return time series points (per_run by default), ordered by created_at asc.
    Each point includes run_id for traceability."""
    raw_points = get_trends(tenant_id, days=days, mode="per_run")
    # Repo returns desc; reverse for asc (oldest first)
    points = [
        MetricsTrendPoint(
            ts=p["ts"],
            mention_rate=p["mention_rate"],
            citation_rate=p["citation_rate"],
            attribution_accuracy=p["attribution_accuracy"],
            hallucinations=p["hallucinations"],
            composite_index=p["composite_index"],
            run_id=p.get("run_id"),
        )
        for p in reversed(raw_points)
    ]
    return MetricsTrendsResponse(tenant_id=tenant_id, points=points)
