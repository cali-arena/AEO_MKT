"""entity_mentions table. Links entities to sections via mention spans."""

import uuid

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from apps.api.models.base import Base


class EntityMention(Base):
    __tablename__ = "entity_mentions"
    __table_args__ = (
        Index("ix_entity_mentions_tenant_id", "tenant_id", "mention_id"),
        Index("ix_entity_mentions_tenant_entity", "tenant_id", "entity_id"),
        Index("ix_entity_mentions_tenant_section", "tenant_id", "section_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    mention_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    section_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
