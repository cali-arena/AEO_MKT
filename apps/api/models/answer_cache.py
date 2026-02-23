"""answer_cache model. Tenant-scoped answer cache storage."""

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from apps.api.models.base import Base


class AnswerCache(Base):
    """Cached answer payloads per tenant and query hash."""

    __tablename__ = "answer_cache"
    __table_args__ = (
        Index("ix_answer_cache_tenant_id", "tenant_id"),
        Index("ix_answer_cache_expires_at", "expires_at"),
        Index("ix_answer_cache_query_hash", "query_hash"),
    )

    cache_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # index via __table_args__
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
    )
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
