"""ec_versions table. Stores ec_version_hash per tenant."""

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from apps.api.models.base import Base


class ECVersion(Base):
    __tablename__ = "ec_versions"

    tenant_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
