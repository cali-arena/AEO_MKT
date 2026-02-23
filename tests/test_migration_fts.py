"""Smoke test: FTS migration (text_tsv, GIN index) applied correctly."""

import pytest
from sqlalchemy import text

from apps.api.db import engine
from apps.api.tests.conftest import requires_db


@requires_db
def test_text_tsv_column_exists() -> None:
    """Migration 001: sections.text_tsv column exists."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'sections' AND column_name = 'text_tsv'
            """
            )
        ).fetchone()
    assert row is not None, "sections.text_tsv column should exist"
    assert row[1] == "tsvector"


@requires_db
def test_text_tsv_gin_index_exists() -> None:
    """Migration 001: GIN index on text_tsv exists."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'sections' AND indexname = 'ix_sections_text_tsv'
            """
            )
        ).fetchone()
    assert row is not None, "ix_sections_text_tsv GIN index should exist"


@requires_db
def test_text_tsv_backfill_for_existing_rows() -> None:
    """GENERATED STORED: text_tsv populated for existing sections (backfill)."""
    from apps.api.services.repo import insert_raw_page, insert_sections

    tenant_id = "tenant_fts_smoke"
    url = "https://example.com/fts-smoke"
    pid = insert_raw_page(tenant_id, url, text="FTS smoke")
    insert_sections(
        tenant_id,
        pid,
        [
            {"section_id": "sec_fts_1", "text": "moving relocation storage", "version_hash": "v1"},
        ],
    )
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
            SELECT s.section_id, s.text_tsv IS NOT NULL AS has_tsv
            FROM sections s
            WHERE s.tenant_id = :tid AND s.section_id = 'sec_fts_1'
            """
            ),
            {"tid": tenant_id},
        ).fetchone()
    assert row is not None, "section should exist"
    assert row[1] is True, "text_tsv should be populated (GENERATED STORED backfill)"
