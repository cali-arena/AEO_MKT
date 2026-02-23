"""monitor_event model. Tenant-scoped monitor events."""

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from apps.api.models.base import Base


class MonitorEvent(Base):
    """Monitor event: leakage_fail, leakage_pass, refusal_spike, citation_drop, cache_hit_drop."""

    __tablename__ = "monitor_event"
    __table_args__ = (
        Index("ix_monitor_event_tenant_created", "tenant_id", "created_at", postgresql_ops={"created_at": "DESC"}),
        CheckConstraint(
            "event_type IN ('leakage_fail', 'leakage_pass', 'refusal_spike', 'citation_drop', 'cache_hit_drop')",
            name="ck_monitor_event_type",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high')",
            name="ck_monitor_event_severity",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
