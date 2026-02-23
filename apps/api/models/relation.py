"""relations table. (subject_entity_id, predicate, object_entity_id) per tenant."""

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base


class Relation(Base):
    __tablename__ = "relations"
    __table_args__ = (Index("ix_relations_tenant_subject", "tenant_id", "subject_entity_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    subject_entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    predicate: Mapped[str | None] = mapped_column(String(256), nullable=True)
    object_entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    evidence_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
