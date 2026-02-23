"""entities table. EC storage: tenant_id, entity_id, canonical_name, entity_type, metadata jsonb, timestamps."""

from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from apps.api.models.base import Base


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_id", name="uq_entities_tenant_entity"),
        Index("ix_entities_tenant_id", "tenant_id", "id"),
        Index("ix_entities_tenant_canonical_name", "tenant_id", "canonical_name"),
        Index("ix_entities_tenant_section", "tenant_id", "section_id"),
        Index("ix_entities_tenant_name", "tenant_id", "name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    canonical_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    entity_type: Mapped[str | None] = mapped_column("type", String(128), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
    # Legacy: kept for backward compatibility during migration
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    section_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # indexed via __table_args__
    evidence_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # indexed via __table_args__
