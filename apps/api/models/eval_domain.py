"""eval_domain model. User-added domains to evaluate (included in 24/7 cron)."""

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base


class EvalDomain(Base):
    """Domain added by user for evaluation; cron runs eval for these 24/7."""

    __tablename__ = "eval_domain"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
