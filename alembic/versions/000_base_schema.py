"""Base schema: raw_page, sections (without text_tsv), evidence, entities, entity_mentions, relations, ec_versions, ac_embeddings, ec_embeddings.

Migration 001 adds text_tsv to sections.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "000_base"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Embedding dimension (bge-small-en-v1.5 = 384)
EMBEDDING_DIM = 384


def upgrade() -> None:
    # 1) raw_page (sections depends on it)
    op.create_table(
        "raw_page",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, index=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("html", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True, index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("page_type", sa.String(64), nullable=True),
        sa.Column("crawl_policy_version", sa.String(12), nullable=True),
        sa.Column("crawl_decision", sa.String(32), nullable=True),
        sa.Column("crawl_reason", sa.String(512), nullable=True),
    )
    op.create_index("ix_raw_page_tenant_id", "raw_page", ["tenant_id", "id"], unique=False, if_not_exists=True)

    # 2) sections (without text_tsv; 001 adds it)
    op.create_table(
        "sections",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("raw_page_id", sa.BigInteger(), sa.ForeignKey("raw_page.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", sa.String(255), nullable=False, index=True),
        sa.Column("heading_path", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("start_char", sa.Integer(), nullable=True),
        sa.Column("end_char", sa.Integer(), nullable=True),
        sa.Column("section_hash", sa.String(64), nullable=True, index=True),
        sa.Column("version_hash", sa.String(64), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("page_type", sa.String(64), nullable=True),
        sa.Column("crawl_policy_version", sa.String(12), nullable=True),
    )
    op.create_index("ix_sections_tenant_id", "sections", ["tenant_id", "id"], unique=False, if_not_exists=True)

    # 3) evidence
    op.create_table(
        "evidence",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("evidence_id", sa.String(255), nullable=False, index=True),
        sa.Column("section_id", sa.String(255), nullable=False, index=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("quote_span", sa.Text(), nullable=True),
        sa.Column("start_char", sa.Integer(), nullable=True),
        sa.Column("end_char", sa.Integer(), nullable=True),
        sa.Column("version_hash", sa.String(64), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_evidence_tenant_id", "evidence", ["tenant_id", "id"], unique=False, if_not_exists=True)

    # 4) entities
    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False, index=True),
        sa.Column("canonical_name", sa.String(512), nullable=True),
        sa.Column("type", sa.String(128), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("section_id", sa.String(255), nullable=True, index=True),
        sa.Column("evidence_id", sa.String(255), nullable=True, index=True),
        sa.UniqueConstraint("tenant_id", "entity_id", name="uq_entities_tenant_entity"),
    )
    op.create_index("ix_entities_tenant_id", "entities", ["tenant_id", "id"], unique=False, if_not_exists=True)
    op.create_index("ix_entities_tenant_canonical_name", "entities", ["tenant_id", "canonical_name"], unique=False, if_not_exists=True)
    op.create_index("ix_entities_tenant_section", "entities", ["tenant_id", "section_id"], unique=False, if_not_exists=True)
    op.create_index("ix_entities_tenant_name", "entities", ["tenant_id", "name"], unique=False, if_not_exists=True)

    # 5) entity_mentions
    op.create_table(
        "entity_mentions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("mention_id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_id", sa.String(255), nullable=False, index=True),
        sa.Column("section_id", sa.String(255), nullable=False, index=True),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("quote_span", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_entity_mentions_tenant_id", "entity_mentions", ["tenant_id", "mention_id"], unique=False, if_not_exists=True)
    op.create_index("ix_entity_mentions_tenant_entity", "entity_mentions", ["tenant_id", "entity_id"], unique=False, if_not_exists=True)
    op.create_index("ix_entity_mentions_tenant_section", "entity_mentions", ["tenant_id", "section_id"], unique=False, if_not_exists=True)

    # 6) relations
    op.create_table(
        "relations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("subject_entity_id", sa.String(255), nullable=False, index=True),
        sa.Column("predicate", sa.String(256), nullable=True),
        sa.Column("object_entity_id", sa.String(255), nullable=False, index=True),
        sa.Column("evidence_id", sa.String(255), nullable=True, index=True),
    )
    op.create_index("ix_relations_tenant_subject", "relations", ["tenant_id", "subject_entity_id"], unique=False, if_not_exists=True)

    # 7) ec_versions
    op.create_table(
        "ec_versions",
        sa.Column("tenant_id", sa.String(255), primary_key=True),
        sa.Column("version_hash", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # 8) ac_embeddings (requires pgvector)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "ac_embeddings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("section_id", sa.String(255), nullable=False, index=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
    )
    op.create_index("ix_ac_embeddings_tenant_section", "ac_embeddings", ["tenant_id", "section_id"], unique=False, if_not_exists=True)

    # 9) ec_embeddings
    op.create_table(
        "ec_embeddings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False, index=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("dim", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_ec_embeddings_tenant_entity", "ec_embeddings", ["tenant_id", "entity_id"], unique=False, if_not_exists=True)
    op.create_index("ix_ec_embeddings_tenant_id", "ec_embeddings", ["tenant_id", "id"], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_ec_embeddings_tenant_id", table_name="ec_embeddings")
    op.drop_index("ix_ec_embeddings_tenant_entity", table_name="ec_embeddings")
    op.drop_table("ec_embeddings")
    op.drop_index("ix_ac_embeddings_tenant_section", table_name="ac_embeddings")
    op.drop_table("ac_embeddings")
    op.drop_table("ec_versions")
    op.drop_index("ix_relations_tenant_subject", table_name="relations")
    op.drop_table("relations")
    op.drop_index("ix_entity_mentions_tenant_section", table_name="entity_mentions")
    op.drop_index("ix_entity_mentions_tenant_entity", table_name="entity_mentions")
    op.drop_index("ix_entity_mentions_tenant_id", table_name="entity_mentions")
    op.drop_table("entity_mentions")
    op.drop_index("ix_entities_tenant_name", table_name="entities")
    op.drop_index("ix_entities_tenant_section", table_name="entities")
    op.drop_index("ix_entities_tenant_canonical_name", table_name="entities")
    op.drop_index("ix_entities_tenant_id", table_name="entities")
    op.drop_table("entities")
    op.drop_index("ix_evidence_tenant_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_sections_tenant_id", table_name="sections")
    op.drop_table("sections")
    op.drop_index("ix_raw_page_tenant_id", table_name="raw_page")
    op.drop_table("raw_page")
