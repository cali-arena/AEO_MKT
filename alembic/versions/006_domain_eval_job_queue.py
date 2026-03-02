"""Add persistent domain evaluation job queue.

Revision ID: 006_domain_eval_job_queue
Revises: 005_eval_domain
Create Date: 2026-03-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "006_domain_eval_job_queue"
down_revision: Union[str, None] = "005_eval_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_eval_job",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("domains", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("total", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("completed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')", name="ck_domain_eval_job_status"),
    )
    op.create_index("ix_domain_eval_job_tenant", "domain_eval_job", ["tenant_id"], unique=False)
    op.create_index(
        "ix_domain_eval_job_tenant_status_created",
        "domain_eval_job",
        ["tenant_id", "status", "created_at"],
        unique=False,
    )
    op.create_index("ix_domain_eval_job_lease", "domain_eval_job", ["status", "lease_expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_domain_eval_job_lease", table_name="domain_eval_job")
    op.drop_index("ix_domain_eval_job_tenant_status_created", table_name="domain_eval_job")
    op.drop_index("ix_domain_eval_job_tenant", table_name="domain_eval_job")
    op.drop_table("domain_eval_job")
