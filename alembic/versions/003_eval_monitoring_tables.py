"""Add eval_run, eval_result, monitor_event, ingestion_stats_daily for eval/monitoring.

Revision ID: 003_eval_monitor
Revises: 002_index_cache
Create Date: 2025-02-20 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "003_eval_monitor"
down_revision: Union[str, None] = "002_index_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) eval_run
    op.create_table(
        "eval_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("git_sha", sa.Text(), nullable=True),
        sa.Column("crawl_policy_version", sa.Text(), nullable=False),
        sa.Column("ac_version_hash", sa.Text(), nullable=False),
        sa.Column("ec_version_hash", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_eval_run_tenant_created",
        "eval_run",
        ["tenant_id", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )

    # 2) eval_result
    op.create_table(
        "eval_result",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("eval_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("query_id", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("refused", sa.Boolean(), nullable=False),
        sa.Column("refusal_reason", sa.Text(), nullable=True),
        sa.Column("mention_ok", sa.Boolean(), nullable=False),
        sa.Column("citation_ok", sa.Boolean(), nullable=False),
        sa.Column("attribution_ok", sa.Boolean(), nullable=False),
        sa.Column("hallucination_flag", sa.Boolean(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("avg_confidence", sa.Float(), nullable=False),
        sa.Column("top_cited_urls", JSONB(), nullable=True),
        sa.Column("answer_preview", sa.Text(), nullable=True),
    )
    op.create_index("ix_eval_result_tenant_run", "eval_result", ["tenant_id", "run_id"], unique=False)
    op.create_index("ix_eval_result_tenant_domain", "eval_result", ["tenant_id", "domain"], unique=False)

    # 3) monitor_event
    op.create_table(
        "monitor_event",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("details_json", JSONB(), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('leakage_fail', 'refusal_spike', 'citation_drop', 'cache_hit_drop')",
            name="ck_monitor_event_type",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high')",
            name="ck_monitor_event_severity",
        ),
    )
    op.create_index(
        "ix_monitor_event_tenant_created",
        "monitor_event",
        ["tenant_id", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )

    # 4) ingestion_stats_daily (optional)
    op.create_table(
        "ingestion_stats_daily",
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("pages_indexed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pages_excluded", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("excluded_by_reason", JSONB(), nullable=True),
        sa.Column("sections_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_section_chars", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "domain", "date"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_stats_daily")

    op.drop_index("ix_monitor_event_tenant_created", table_name="monitor_event")
    op.drop_table("monitor_event")

    op.drop_index("ix_eval_result_tenant_domain", table_name="eval_result")
    op.drop_index("ix_eval_result_tenant_run", table_name="eval_result")
    op.drop_table("eval_result")

    op.drop_index("ix_eval_run_tenant_created", table_name="eval_run")
    op.drop_table("eval_run")
