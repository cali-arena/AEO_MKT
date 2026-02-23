"""Response schemas for API endpoints. Contract-frozen: extra fields forbidden."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RetrieveCandidate(BaseModel):
    """A single retrieval candidate. Hybrid: merged_score, vector_score, bm25_score + rerank."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    merged_score: float
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rerank_score: float = 0.0
    rerank_reasons: list[str] = Field(default_factory=list)
    url: str
    version_hash: str
    snippet: str


class RetrieveDebugVector(BaseModel):
    """Debug info for vector or bm25 retrieval branch. Stable contract: always fixed keys."""

    model_config = ConfigDict(extra="forbid")

    requested_k: int
    returned_k: int
    min: float = 0.0  # 0 when channel empty
    max: float = 0.0  # 0 when channel empty
    top_scores: list[float] = Field(default_factory=list, description="Top 5 scores")


class RetrieveDebugMerge(BaseModel):
    """Debug info for merge/dedup step."""

    model_config = ConfigDict(extra="forbid")

    weights: dict[str, float] = Field(default_factory=dict)
    deduped_count: int = 0
    final_k: int = 0


class RetrieveDebug(BaseModel):
    """Debug info for retrieval response. Always present."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    vector: RetrieveDebugVector
    bm25: RetrieveDebugVector
    merge: RetrieveDebugMerge


class RetrieveResponse(BaseModel):
    """Response for POST /retrieve/ac. Section-level candidates."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[RetrieveCandidate] = Field(default_factory=list)
    debug: RetrieveDebug


# EC-specific schemas: entity-level results

class ECMention(BaseModel):
    """A single mention of an entity in a section."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    start_offset: int
    end_offset: int
    quote_span: str
    url: str = ""


class RetrieveECCandidate(BaseModel):
    """A single EC retrieval result: entity with score and mentions."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str
    score: float
    canonical_name: str = ""
    entity_type: str = ""
    mentions: list[ECMention] = Field(default_factory=list)


class RetrieveECDebug(BaseModel):
    """Debug info for EC retrieval response. Stable contract: fixed keys only."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    vector: bool = True
    entity_count: int = 0


class RetrieveECResponse(BaseModel):
    """Response for POST /retrieve/ec. Entity-level candidates."""

    model_config = ConfigDict(extra="forbid")

    entities: list[RetrieveECCandidate] = Field(default_factory=list)
    debug: RetrieveECDebug


class Evidence(BaseModel):
    """Evidence record. Contract-frozen for serialization."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    tenant_id: str
    section_id: str
    url: str
    quote_span: str
    start_char: int
    end_char: int
    version_hash: str
    created_at: datetime


class Claim(BaseModel):
    """A claim in the answer response."""

    model_config = ConfigDict(extra="forbid")

    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float


class AnswerDraft(BaseModel):
    """LLM output schema: answer + claims. Must be valid JSON with no prose outside."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    claims: list[Claim] = Field(default_factory=list)


class Citation(BaseModel):
    """Citation for evidence_id. Maps to retrieved evidence."""

    model_config = ConfigDict(extra="forbid")

    url: str
    section_id: str
    quote_span: str


class AnswerDebug(BaseModel):
    """Debug for /answer retrieval confidence gate."""

    model_config = ConfigDict(extra="forbid")

    threshold: float
    top_score: float | None = None


class AnswerResponse(BaseModel):
    """Response for POST /answer."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    claims: list[Claim] = Field(default_factory=list)
    citations: dict[str, Citation] = Field(default_factory=dict)
    debug: AnswerDebug | None = None
    refused: bool
    refusal_reason: str | None = None
