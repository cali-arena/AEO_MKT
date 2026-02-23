-- Add text_tsv for FTS on sections. Uses GENERATED STORED.
-- Run: psql $DATABASE_URL -f apps/api/migrations/add_sections_text_tsv.sql
-- Prefer: alembic upgrade head (uses FTS_LANG env, default 'simple').

ALTER TABLE sections ADD COLUMN IF NOT EXISTS text_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('simple', COALESCE(text, ''))) STORED;

CREATE INDEX IF NOT EXISTS ix_sections_text_tsv ON sections USING GIN (text_tsv);
