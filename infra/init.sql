-- Enable pgvector for embedding similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- FTS on sections.text: handled by Alembic migration 001_add_sections_text_tsv.
-- Config via FTS_LANG env (default: simple). No extension needed (built-in).
