"""ac_embeddings model."""

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from apps.api.models.base import Base


# Embedding dimension (bge-small-en-v1.5 = 384)
EMBEDDING_DIM = 384


class ACEmbedding(Base):
    __tablename__ = "ac_embeddings"
    __table_args__ = (Index("ix_ac_embeddings_tenant_section", "tenant_id", "section_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    section_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

