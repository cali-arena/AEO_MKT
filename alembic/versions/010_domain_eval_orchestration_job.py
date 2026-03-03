"""Add domain_eval_orchestration_job table.

Revision ID: 010_domain_eval_orchestration_job
Revises: 009_domain_eval_job_error_code
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "010_domain_eval_orchestration_job"
down_revision: Union[str, None] = "009_domain_eval_job_error_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_eval_orchestration_job",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("domains", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("desired_hashes_per_domain", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("eval_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')",
            name="ck_domain_eval_orchestration_job_status",
        ),
    )
    op.create_index(
        "ix_domain_eval_orchestration_job_tenant_status",
        "domain_eval_orchestration_job",
        ["tenant_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_domain_eval_orchestration_job_tenant_status", table_name="domain_eval_orchestration_job")
    op.drop_table("domain_eval_orchestration_job")
