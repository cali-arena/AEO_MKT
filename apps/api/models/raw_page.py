"""raw_page model."""

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from apps.api.models.base import Base


class RawPage(Base):
    __tablename__ = "raw_page"
    __table_args__ = (Index("ix_raw_page_tenant_id", "tenant_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)  # indexed via __table_args__
    url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    html: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=False)
    page_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=False)
    crawl_policy_version: Mapped[str | None] = mapped_column(String(12), nullable=True, index=False)
    crawl_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    crawl_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    sections = relationship("Section", back_populates="raw_page", cascade="all, delete-orphan")
