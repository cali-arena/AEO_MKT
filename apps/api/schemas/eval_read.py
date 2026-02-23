"""Eval read endpoints response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.metrics import MetricsKPIs


class EvalRunListItem(BaseModel):
    """Single eval run in runs list response."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    created_at: datetime
    crawl_policy_version: str
    ac_version_hash: str
    ec_version_hash: str
    kpis_summary: MetricsKPIs


class EvalRunsResponse(BaseModel):
    """Response for eval runs list endpoint."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    runs: list[EvalRunListItem] = Field(default_factory=list)


class EvalResultRow(BaseModel):
    """Single eval result row for worst queries table."""

    model_config = ConfigDict(extra="forbid")

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


class EvalRunResultsResponse(BaseModel):
    """Response for eval run results endpoint."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    run_id: UUID
    results: list[EvalResultRow] = Field(default_factory=list)
