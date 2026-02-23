"""Add sections.text_tsv for FTS.

Revision ID: 001_text_tsv
Revises:
Create Date: 2025-01-01 00:00:00

"""
import os
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "001_text_tsv"
down_revision: Union[str, None] = "000_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fts_config() -> str:
    """FTS config from FTS_LANG env, default 'simple'. Sanitized for SQL."""
    raw = (os.getenv("FTS_LANG") or "simple").strip() or "simple"
    if re.match(r"^[a-zA-Z0-9_]+$", raw):
        return raw
    return "simple"


def upgrade() -> None:
    """Add text_tsv tsvector column (GENERATED STORED). Config from FTS_LANG env."""
    config = _fts_config()
    conn = op.get_bind()

    # GENERATED STORED: config must be literal in DDL
    conn.execute(
        text(
            f"ALTER TABLE sections ADD COLUMN IF NOT EXISTS text_tsv tsvector "
            f"GENERATED ALWAYS AS (to_tsvector('{config}', COALESCE(text, ''))) STORED"
        )
    )
    op.create_index(
        "ix_sections_text_tsv",
        "sections",
        ["text_tsv"],
        unique=False,
        postgresql_using="gin",
        if_not_exists=True,
    )


def downgrade() -> None:
    """Remove text_tsv column and index."""
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS ix_sections_text_tsv"))
    conn.execute(text("ALTER TABLE sections DROP COLUMN IF EXISTS text_tsv"))
