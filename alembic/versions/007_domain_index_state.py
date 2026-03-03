"""Add domain_index_state table for per-tenant, per-domain index state.

Revision ID: 007_domain_index_state
Revises: 006_domain_eval_job_queue
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_domain_index_state"
down_revision: Union[str, None] = "006_domain_eval_job_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_index_state",
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("ac_version_hash", sa.Text(), nullable=True),
        sa.Column("ec_version_hash", sa.Text(), nullable=True),
        sa.Column("crawl_policy_version", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("tenant_id", "domain", name="pk_domain_index_state"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')",
            name="ck_domain_index_state_status",
        ),
    )
    op.create_index(
        "ix_domain_index_state_tenant_status",
        "domain_index_state",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_domain_index_state_tenant_domain",
        "domain_index_state",
        ["tenant_id", "domain"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_domain_index_state_tenant_domain", table_name="domain_index_state")
    op.drop_index("ix_domain_index_state_tenant_status", table_name="domain_index_state")
    op.drop_table("domain_index_state")
