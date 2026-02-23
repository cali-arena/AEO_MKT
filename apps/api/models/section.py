"""sections model.

FTS: sections.text_tsv is a tsvector for full-text search on sections.text.
- Migration (alembic 001): adds text_tsv via FTS_LANG env (default 'simple').
- ensure_tables: creates with 'simple' from model Computed.
- bm25_retrieve_sections uses FTS_LANG at query time.
"""

from typing import Any

from sqlalchemy import BigInteger, Computed, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from apps.api.models.base import Base


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        Index("ix_sections_tenant_id", "tenant_id", "id"),
        Index("ix_sections_text_tsv", "text_tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    raw_page_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("raw_page.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    heading_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    version_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=False)
    page_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=False)
    crawl_policy_version: Mapped[str | None] = mapped_column(String(12), nullable=True, index=False)
    # FTS: config via FTS_LANG (default 'simple')
    text_tsv: Mapped[Any | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', COALESCE(text, ''))", persisted=True),
        nullable=True,
    )

    raw_page = relationship("RawPage", back_populates="sections")
