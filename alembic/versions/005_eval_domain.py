"""Add eval_domain table for user-added domains to evaluate 24/7.

Revision ID: 005_eval_domain
Revises: 004_leakage_pass
Create Date: 2025-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_eval_domain"
down_revision: Union[str, None] = "004_leakage_pass"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eval_domain",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eval_domain_tenant", "eval_domain", ["tenant_id"], unique=False)
    op.create_unique_constraint("uq_eval_domain_tenant_domain", "eval_domain", ["tenant_id", "domain"])


def downgrade() -> None:
    op.drop_constraint("uq_eval_domain_tenant_domain", "eval_domain", type_="unique")
    op.drop_index("ix_eval_domain_tenant", table_name="eval_domain")
    op.drop_table("eval_domain")
