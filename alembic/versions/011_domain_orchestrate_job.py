"""Add domain_orchestrate_job table (Way 1: sequential ensure->ingest->eval in worker).

Revision ID: 011_domain_orchestrate_job
Revises: 010_domain_eval_orchestration_job
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "011_domain_orchestrate_job"
down_revision: Union[str, None] = "010_domain_eval_orchestration_job"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_orchestrate_job",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("domains", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("desired_by_domain", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("completed_domains", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')",
            name="ck_domain_orchestrate_job_status",
        ),
    )
    op.create_index(
        "ix_domain_orchestrate_job_tenant_status",
        "domain_orchestrate_job",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_domain_orchestrate_job_created",
        "domain_orchestrate_job",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_domain_orchestrate_job_created", table_name="domain_orchestrate_job")
    op.drop_index("ix_domain_orchestrate_job_tenant_status", table_name="domain_orchestrate_job")
    op.drop_table("domain_orchestrate_job")
