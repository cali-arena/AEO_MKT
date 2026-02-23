"""eval_result model. Tenant-scoped eval result per run."""

import uuid

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.models.base import Base


class EvalResult(Base):
    """Eval result: per-run metrics (refused, mention_ok, citation_ok, etc)."""

    __tablename__ = "eval_result"
    __table_args__ = (
        Index("ix_eval_result_tenant_run", "tenant_id", "run_id"),
        Index("ix_eval_result_tenant_domain", "tenant_id", "domain"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    query_id: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    refused: Mapped[bool] = mapped_column(Boolean, nullable=False)
    refusal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    mention_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    citation_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attribution_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hallucination_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    top_cited_urls: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    answer_preview: Mapped[str | None] = mapped_column(Text, nullable=True)

    run = relationship("EvalRun", back_populates="results")
