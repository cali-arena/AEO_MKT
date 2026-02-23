"""Pydantic schemas for eval and monitor dashboard. tenant_id from auth only."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Create schema (for bulk insert)
# ---------------------------------------------------------------------------


class EvalResultCreate(BaseModel):
    """Payload for a single eval result in bulk insert."""

    model_config = ConfigDict(extra="forbid")

    query_id: str
    domain: str
    query_text: str
    refused: bool
    refusal_reason: str | None = None
    mention_ok: bool
    citation_ok: bool
    attribution_ok: bool
    hallucination_flag: bool
    evidence_count: int
    avg_confidence: float
    top_cited_urls: dict | list | None = None
    answer_preview: str | None = None


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class EvalRunOut(BaseModel):
    """Eval run output. JSON-serializable."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    tenant_id: str
    created_at: datetime
    git_sha: str | None
    crawl_policy_version: str
    ac_version_hash: str
    ec_version_hash: str


class EvalResultOut(BaseModel):
    """Eval result output. JSON-serializable."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    run_id: UUID
    tenant_id: str
    query_id: str
    domain: str
    query_text: str
    refused: bool
    refusal_reason: str | None
    mention_ok: bool
    citation_ok: bool
    attribution_ok: bool
    hallucination_flag: bool
    evidence_count: int
    avg_confidence: float
    top_cited_urls: dict | list | None
    answer_preview: str | None


class MonitorEventOut(BaseModel):
    """Monitor event output. JSON-serializable."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    tenant_id: str
    created_at: datetime
    event_type: str
    severity: str
    details_json: dict | list | None


class IngestionStatsDailyOut(BaseModel):
    """Ingestion stats daily output. JSON-serializable."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    domain: str
    date: date
    pages_indexed: int
    pages_excluded: int
    excluded_by_reason: dict | list | None
    sections_count: int
    avg_section_chars: float | None


# ---------------------------------------------------------------------------
# Eval run with summary
# ---------------------------------------------------------------------------


class EvalRunWithSummaryOut(BaseModel):
    """Eval run + aggregate summary counts for dashboard."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: str
    created_at: datetime
    git_sha: str | None
    crawl_policy_version: str
    ac_version_hash: str
    ec_version_hash: str
    total: int = Field(..., description="Total results in run")
    refused_count: int = Field(..., description="Number of refused results")
    citation_ok_count: int = Field(..., description="Results with citation_ok=True")
    citation_ok_rate: float = Field(..., description="citation_ok_count / total (0 if total=0)")
    mention_ok_count: int = Field(..., description="Results with mention_ok=True")
    attribution_ok_count: int = Field(..., description="Results with attribution_ok=True")
    hallucination_count: int = Field(..., description="Results with hallucination_flag=True")


# ---------------------------------------------------------------------------
# Query filters (client payload: domain, date range, query_id only)
# ---------------------------------------------------------------------------


class EvalMetricsRates(BaseModel):
    """Aggregated rates for a set of eval results."""

    model_config = ConfigDict(extra="forbid")

    mention_rate: float
    citation_rate: float
    attribution_rate: float
    hallucination_rate: float


class EvalMetricsLatestOut(BaseModel):
    """Response for GET /eval/metrics/latest."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    overall: EvalMetricsRates
    per_domain: dict[str, EvalMetricsRates]


# ---------------------------------------------------------------------------
# Query filters (client payload: domain, date range, query_id only)
# ---------------------------------------------------------------------------


class QueryFilters(BaseModel):
    """Filters for eval/monitor queries. tenant_id comes from auth, NOT from client."""

    model_config = ConfigDict(extra="forbid")

    domain: str | None = Field(None, description="Filter by domain")
    date_from: date | None = Field(None, description="Start date (inclusive)")
    date_to: date | None = Field(None, description="End date (inclusive)")
    query_id: str | None = Field(None, description="Filter by query_id")
