"""Add domain_ingest_job table.

Revision ID: 008_domain_ingest_job
Revises: 007_domain_index_state
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "008_domain_ingest_job"
down_revision: Union[str, None] = "007_domain_index_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_ingest_job",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("desired_ac_version_hash", sa.Text(), nullable=True),
        sa.Column("desired_ec_version_hash", sa.Text(), nullable=True),
        sa.Column("desired_crawl_policy_version", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')",
            name="ck_domain_ingest_job_status",
        ),
    )
    op.create_index(
        "ix_domain_ingest_job_tenant_domain_status",
        "domain_ingest_job",
        ["tenant_id", "domain", "status"],
        unique=False,
    )
    op.create_index(
        "ix_domain_ingest_job_tenant_created",
        "domain_ingest_job",
        ["tenant_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_domain_ingest_job_tenant_created", table_name="domain_ingest_job")
    op.drop_index("ix_domain_ingest_job_tenant_domain_status", table_name="domain_ingest_job")
    op.drop_table("domain_ingest_job")
