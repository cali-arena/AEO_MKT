"""Add tenant_id+domain to sections/embeddings/evidence; backfill and indexes.

- raw_page: domain already exists (nullable). Backfill from URL, set NOT NULL, add index.
- sections: domain already exists (nullable). Backfill from raw_page, set NOT NULL, add indexes.
- evidence: add domain, backfill from sections, add indexes.
- ac_embeddings: add domain, backfill from sections, add index.
- ec_embeddings: add domain, backfill via entities->sections, add indexes.

No table renames. No data drops.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_tenant_domain_sections_embeddings_evidence"
down_revision: Union[str, None] = "012_orchestrate_job_current_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- raw_page: backfill domain from URL where null, then NOT NULL + index ---
    op.execute(
        sa.text("""
            UPDATE raw_page
            SET domain = COALESCE(
                NULLIF(TRIM(SUBSTRING(canonical_url FROM '://([^/?#]+)')), ''),
                NULLIF(TRIM(SUBSTRING(url FROM '://([^/?#]+)')), '')
            )
            WHERE domain IS NULL
        """)
    )
    op.execute(sa.text("UPDATE raw_page SET domain = '' WHERE domain IS NULL"))
    op.alter_column(
        "raw_page",
        "domain",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.create_index(
        "ix_raw_page_tenant_domain",
        "raw_page",
        ["tenant_id", "domain"],
        unique=False,
    )

    # --- sections: backfill domain from raw_page, then NOT NULL + indexes ---
    op.execute(
        sa.text("""
            UPDATE sections s
            SET domain = COALESCE(r.domain, '')
            FROM raw_page r
            WHERE s.raw_page_id = r.id AND r.tenant_id = s.tenant_id AND (s.domain IS NULL OR s.domain = '')
        """)
    )
    op.execute(sa.text("UPDATE sections SET domain = '' WHERE domain IS NULL"))
    op.alter_column(
        "sections",
        "domain",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.create_index(
        "ix_sections_tenant_domain",
        "sections",
        ["tenant_id", "domain"],
        unique=False,
    )
    op.create_index(
        "ix_sections_tenant_domain_created_at",
        "sections",
        ["tenant_id", "domain", "created_at"],
        unique=False,
    )

    # --- evidence: add domain, backfill from sections, NOT NULL + indexes ---
    op.add_column("evidence", sa.Column("domain", sa.Text(), nullable=True))
    op.execute(
        sa.text("""
            UPDATE evidence e
            SET domain = s.domain
            FROM sections s
            WHERE e.tenant_id = s.tenant_id AND e.section_id = s.section_id
        """)
    )
    op.execute(sa.text("UPDATE evidence SET domain = '' WHERE domain IS NULL"))
    op.alter_column("evidence", "domain", existing_type=sa.Text(), nullable=False)
    op.create_index(
        "ix_evidence_tenant_domain",
        "evidence",
        ["tenant_id", "domain"],
        unique=False,
    )
    op.create_index(
        "ix_evidence_tenant_domain_created_at",
        "evidence",
        ["tenant_id", "domain", "created_at"],
        unique=False,
    )

    # --- ac_embeddings: add domain, backfill from sections, NOT NULL + index ---
    op.add_column("ac_embeddings", sa.Column("domain", sa.Text(), nullable=True))
    op.execute(
        sa.text("""
            UPDATE ac_embeddings ae
            SET domain = s.domain
            FROM sections s
            WHERE ae.tenant_id = s.tenant_id AND ae.section_id = s.section_id
        """)
    )
    op.execute(sa.text("UPDATE ac_embeddings SET domain = '' WHERE domain IS NULL"))
    op.alter_column("ac_embeddings", "domain", existing_type=sa.Text(), nullable=False)
    op.create_index(
        "ix_ac_embeddings_tenant_domain",
        "ac_embeddings",
        ["tenant_id", "domain"],
        unique=False,
    )

    # --- ec_embeddings: add domain, backfill via entities -> sections, NOT NULL + indexes ---
    op.add_column("ec_embeddings", sa.Column("domain", sa.Text(), nullable=True))
    op.execute(
        sa.text("""
            UPDATE ec_embeddings ee
            SET domain = s.domain
            FROM entities ent
            JOIN sections s ON ent.tenant_id = s.tenant_id AND ent.section_id = s.section_id
            WHERE ee.tenant_id = ent.tenant_id AND ee.entity_id = ent.entity_id
        """)
    )
    op.execute(sa.text("UPDATE ec_embeddings SET domain = '' WHERE domain IS NULL"))
    op.alter_column("ec_embeddings", "domain", existing_type=sa.Text(), nullable=False)
    op.create_index(
        "ix_ec_embeddings_tenant_domain",
        "ec_embeddings",
        ["tenant_id", "domain"],
        unique=False,
    )
    op.create_index(
        "ix_ec_embeddings_tenant_domain_created_at",
        "ec_embeddings",
        ["tenant_id", "domain", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ec_embeddings_tenant_domain_created_at", table_name="ec_embeddings")
    op.drop_index("ix_ec_embeddings_tenant_domain", table_name="ec_embeddings")
    op.drop_column("ec_embeddings", "domain")

    op.drop_index("ix_ac_embeddings_tenant_domain", table_name="ac_embeddings")
    op.drop_column("ac_embeddings", "domain")

    op.drop_index("ix_evidence_tenant_domain_created_at", table_name="evidence")
    op.drop_index("ix_evidence_tenant_domain", table_name="evidence")
    op.drop_column("evidence", "domain")

    op.drop_index("ix_sections_tenant_domain_created_at", table_name="sections")
    op.drop_index("ix_sections_tenant_domain", table_name="sections")
    op.alter_column(
        "sections",
        "domain",
        existing_type=sa.String(255),
        nullable=True,
    )

    op.drop_index("ix_raw_page_tenant_domain", table_name="raw_page")
    op.alter_column(
        "raw_page",
        "domain",
        existing_type=sa.String(255),
        nullable=True,
    )
