"""Add leakage_pass to monitor_event event_type constraint.

Revision ID: 004_leakage_pass
Revises: 003_eval_monitor
Create Date: 2025-02-22

"""
from typing import Sequence, Union

from alembic import op

revision: str = "004_leakage_pass"
down_revision: Union[str, None] = "003_eval_monitor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_monitor_event_type", "monitor_event", type_="check")
    op.create_check_constraint(
        "ck_monitor_event_type",
        "monitor_event",
        "event_type IN ('leakage_fail', 'leakage_pass', 'refusal_spike', 'citation_drop', 'cache_hit_drop')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_monitor_event_type", "monitor_event", type_="check")
    op.create_check_constraint(
        "ck_monitor_event_type",
        "monitor_event",
        "event_type IN ('leakage_fail', 'refusal_spike', 'citation_drop', 'cache_hit_drop')",
    )
