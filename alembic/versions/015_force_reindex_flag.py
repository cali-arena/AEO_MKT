"""Add force flag for domain ingest/eval jobs."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_force_reindex_flag"
down_revision: Union[str, None] = "014_domain_index_state_error_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "domain_ingest_job",
        sa.Column("force", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "domain_eval_job",
        sa.Column("force", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("domain_eval_job", "force")
    op.drop_column("domain_ingest_job", "force")

