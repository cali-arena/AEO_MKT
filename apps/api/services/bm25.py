"""FTS-based BM25 retrieval for AC sections.

Uses websearch_to_tsquery and ts_rank_cd with sections.text_tsv.
Requires text_tsv column (run add_sections_text_tsv.sql migration).
"""

import os
from typing import Any

from sqlalchemy import text

from apps.api.db import get_db
from apps.api.services.repo import _assert_tenant


def bm25_retrieve_sections(
    tenant_id: str | None,
    query: str,
    k: int = 20,
    fts_config: str | None = None,
) -> list[dict[str, Any]]:
    """
    FTS-based retrieval for AC sections. Returns list of {section_id, bm25_score}.

    Uses websearch_to_tsquery and ts_rank_cd(text_tsv, tsquery).
    Enforces tenant filter at SQL layer. Deterministic ordering (secondary sort by section_id).
    """
    _assert_tenant(tenant_id)
    config = (fts_config or os.getenv("FTS_LANG", "simple")).strip() or "simple"
    if not query or not query.strip():
        return []

    q = query.strip()
    sql = text("""
        SELECT s.section_id,
               ts_rank_cd(s.text_tsv, websearch_to_tsquery(:config, :query))::float AS bm25_score
        FROM sections s
        WHERE s.tenant_id = :tenant_id
          AND s.text_tsv @@ websearch_to_tsquery(:config, :query)
        ORDER BY bm25_score DESC, s.section_id ASC
        LIMIT :k
    """)
    with get_db() as session:
        rows = session.execute(
            sql,
            {"tenant_id": tenant_id, "query": q, "config": config, "k": k},
        ).fetchall()

    return [{"section_id": r[0], "bm25_score": float(r[1])} for r in rows]
