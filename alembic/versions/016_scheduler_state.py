"""Add scheduler_state table for auto-eval last tick timestamp."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016_scheduler_state"
down_revision: Union[str, None] = "015_force_reindex_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduler_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("last_tick_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO scheduler_state (id, updated_at) VALUES (1, now())")


def downgrade() -> None:
    op.drop_table("scheduler_state")
