"""tenant_index_versions model. Tenant-scoped index version tracking."""

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from apps.api.models.base import Base


class TenantIndexVersion(Base):
    """Tracks AC/EC index version hashes per tenant."""

    __tablename__ = "tenant_index_versions"

    tenant_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    ac_version_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ec_version_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
