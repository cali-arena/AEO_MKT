"""Add tenant_index_versions and answer_cache.

Revision ID: 002_index_cache
Revises: 001_text_tsv
Create Date: 2025-02-01 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_index_cache"
down_revision: Union[str, None] = "001_text_tsv"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_index_versions",
        sa.Column("tenant_id", sa.String(255), primary_key=True),
        sa.Column("ac_version_hash", sa.String(64), nullable=True),
        sa.Column("ec_version_hash", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    op.create_table(
        "answer_cache",
        sa.Column("cache_key", sa.String(255), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_answer_cache_tenant_id", "answer_cache", ["tenant_id"], unique=False, if_not_exists=True)
    op.create_index("ix_answer_cache_expires_at", "answer_cache", ["expires_at"], unique=False, if_not_exists=True)
    op.create_index("ix_answer_cache_query_hash", "answer_cache", ["query_hash"], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_answer_cache_query_hash", table_name="answer_cache")
    op.drop_index("ix_answer_cache_expires_at", table_name="answer_cache")
    op.drop_index("ix_answer_cache_tenant_id", table_name="answer_cache")
    op.drop_table("answer_cache")
    op.drop_table("tenant_index_versions")
