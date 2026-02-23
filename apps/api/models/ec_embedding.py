"""ec_embeddings table. (tenant_id, entity_id) with vector embedding, model, dim, created_at."""

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from apps.api.models.ac_embedding import EMBEDDING_DIM
from apps.api.models.base import Base


class ECEmbedding(Base):
    __tablename__ = "ec_embeddings"
    __table_args__ = (
        Index("ix_ec_embeddings_tenant_entity", "tenant_id", "entity_id"),
        Index("ix_ec_embeddings_tenant_id", "tenant_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)

