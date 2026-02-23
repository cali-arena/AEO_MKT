"""eval_run model. Tenant-scoped eval run metadata."""

import uuid

from sqlalchemy import DateTime, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from apps.api.models.base import Base


class EvalRun(Base):
    """Eval run: tenant + version hashes + git_sha. Links to eval_result."""

    __tablename__ = "eval_run"
    __table_args__ = (
        Index("ix_eval_run_tenant_created", "tenant_id", "created_at", postgresql_ops={"created_at": "DESC"}),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    git_sha: Mapped[str | None] = mapped_column(Text, nullable=True)
    crawl_policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    ac_version_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ec_version_hash: Mapped[str] = mapped_column(Text, nullable=False)

    results = relationship("EvalResult", back_populates="run", cascade="all, delete-orphan")
