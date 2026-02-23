"""Metrics dashboard response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MetricsKPIs(BaseModel):
    """Aggregated KPIs for an eval run."""

    model_config = ConfigDict(extra="forbid")

    mention_rate: float
    citation_rate: float
    attribution_accuracy: float
    hallucinations: float
    composite_index: float


class MetricsLatestResponse(BaseModel):
    """Response for metrics latest endpoint."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    run_id: UUID
    created_at: datetime
    crawl_policy_version: str
    ac_version_hash: str
    ec_version_hash: str
    kpis: MetricsKPIs


class MetricsTrendPoint(BaseModel):
    """Single point in metrics trend time series."""

    model_config = ConfigDict(extra="forbid")

    ts: str
    mention_rate: float
    citation_rate: float
    attribution_accuracy: float
    hallucinations: float
    composite_index: float
    run_id: UUID | None = None


class MetricsTrendsResponse(BaseModel):
    """Response for metrics trends endpoint."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    points: list[MetricsTrendPoint] = Field(default_factory=list)
