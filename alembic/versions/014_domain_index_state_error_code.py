"""Add error_code to domain_index_state for EMPTY_INDEX etc."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_domain_index_state_error_code"
down_revision: Union[str, None] = "013_tenant_domain_sections_embeddings_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "domain_index_state",
        sa.Column("error_code", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("domain_index_state", "error_code")
