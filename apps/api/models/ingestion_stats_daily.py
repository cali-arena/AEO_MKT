"""ingestion_stats_daily model. Tenant-scoped daily ingestion stats per domain."""

from datetime import date

from sqlalchemy import Date, Float, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from apps.api.models.base import Base


class IngestionStatsDaily(Base):
    """Daily ingestion stats: pages_indexed, pages_excluded, sections_count per tenant/domain/date."""

    __tablename__ = "ingestion_stats_daily"

    tenant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    domain: Mapped[str] = mapped_column(Text, primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    pages_indexed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    pages_excluded: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    excluded_by_reason: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    sections_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    avg_section_chars: Mapped[float | None] = mapped_column(Float, nullable=True)
