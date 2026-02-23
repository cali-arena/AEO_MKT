"""Read-only eval dashboard endpoints. Tenant from auth middleware only."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from apps.api.schemas.eval import EvalMetricsLatestOut, EvalMetricsRates, EvalRunOut, EvalResultOut
from apps.api.schemas.eval_read import EvalResultRow, EvalRunListItem, EvalRunResultsResponse, EvalRunsResponse
from apps.api.schemas.metrics import MetricsKPIs
from apps.api.services.repo import (
    aggregate_kpis_for_run,
    get_eval_metrics_for_run,
    get_eval_results,
    get_latest_eval_run,
    list_eval_results,
    list_eval_runs,
)
from apps.api.services.tenant_context import TenantId

router = APIRouter()


@router.get("/metrics/latest", response_model=EvalMetricsLatestOut)
async def get_metrics_latest(tenant_id: TenantId) -> EvalMetricsLatestOut:
    """Aggregate metrics from latest eval_run for tenant. Group by domain."""
    run = get_latest_eval_run(tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="No eval runs found for tenant")
    metrics = get_eval_metrics_for_run(tenant_id, run.id)
    return EvalMetricsLatestOut(
        run_id=run.id,
        overall=EvalMetricsRates.model_validate(metrics["overall"]),
        per_domain={d: EvalMetricsRates.model_validate(m) for d, m in metrics["per_domain"].items()},
    )


@router.get("/runs", response_model=EvalRunsResponse)
async def list_runs(
    tenant_id: TenantId,
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> EvalRunsResponse:
    """List last N eval runs for tenant (created_at desc) with KPI summary per run."""
    runs = list_eval_runs(tenant_id, limit=limit, offset=offset)
    items: list[EvalRunListItem] = []
    for run in runs:
        kpis_dict = aggregate_kpis_for_run(tenant_id, run.id)
        kpis = MetricsKPIs(
            mention_rate=kpis_dict["mention_rate"],
            citation_rate=kpis_dict["citation_rate"],
            attribution_accuracy=kpis_dict["attribution_accuracy"],
            hallucinations=float(kpis_dict["hallucinations"]),
            composite_index=kpis_dict["composite_index"],
        )
        items.append(
            EvalRunListItem(
                run_id=run.id,
                created_at=run.created_at,
                crawl_policy_version=run.crawl_policy_version,
                ac_version_hash=run.ac_version_hash,
                ec_version_hash=run.ec_version_hash,
                kpis_summary=kpis,
            )
        )
    return EvalRunsResponse(tenant_id=tenant_id, runs=items)


@router.get("/runs/{run_id}/results", response_model=EvalRunResultsResponse)
async def get_run_results(
    run_id: UUID,
    tenant_id: TenantId,
    domain: str | None = Query(None),
    failed_only: bool = Query(False, description="Only rows where refused OR hallucination OR NOT mention_ok OR NOT citation_ok OR NOT attribution_ok"),
    refused_only: bool = Query(False, description="Only refused rows"),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> EvalRunResultsResponse:
    """Get eval results for a run. Tenant-filtered. Order: hallucination_flag desc, refused desc, citation_ok asc, evidence_count asc."""
    results = list_eval_results(
        tenant_id,
        run_id,
        domain=domain,
        failed_only=failed_only,
        refused_only=refused_only,
        limit=limit,
        offset=offset,
    )
    rows = [
        EvalResultRow(
            query_id=r.query_id,
            domain=r.domain,
            query_text=r.query_text,
            refused=r.refused,
            refusal_reason=r.refusal_reason,
            mention_ok=r.mention_ok,
            citation_ok=r.citation_ok,
            attribution_ok=r.attribution_ok,
            hallucination_flag=r.hallucination_flag,
            evidence_count=r.evidence_count,
            avg_confidence=r.avg_confidence,
            top_cited_urls=r.top_cited_urls,
            answer_preview=r.answer_preview,
        )
        for r in results
    ]
    return EvalRunResultsResponse(tenant_id=tenant_id, run_id=run_id, results=rows)
