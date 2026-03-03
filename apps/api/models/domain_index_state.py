"""domain_index_state model. Tracks per-tenant, per-domain index state (AC/EC/crawl version and status)."""

from sqlalchemy import CheckConstraint, DateTime, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from apps.api.models.base import Base


class DomainIndexState(Base):
    """Tracks index state per tenant+domain: version hashes, status, last indexed time."""

    __tablename__ = "domain_index_state"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')",
            name="ck_domain_index_state_status",
        ),
        Index("ix_domain_index_state_tenant_status", "tenant_id", "status"),
        Index("ix_domain_index_state_tenant_domain", "tenant_id", "domain"),
    )

    tenant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    domain: Mapped[str] = mapped_column(Text, primary_key=True)
    ac_version_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    ec_version_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    crawl_policy_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    last_indexed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
