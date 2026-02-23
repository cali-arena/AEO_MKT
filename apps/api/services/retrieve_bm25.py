"""AC BM25 retrieval for hybrid /retrieve/ac. FTS on sections.text_tsv.

Uses websearch_to_tsquery(FTS_LANG, query) and ts_rank_cd(text_tsv, tsquery).
Returns full rows (section_id, version_hash, url, text, page_type, rank) for merge.
"""

import os

from apps.api.services.repo import execute_ac_bm25_retrieval


def retrieve_ac_bm25(
    tenant_id: str,
    query: str,
    k: int = 50,
    fts_config: str | None = None,
) -> list[tuple]:
    """
    BM25 FTS retrieval for hybrid AC. Top-k sections by ts_rank_cd.

    - websearch_to_tsquery(FTS_LANG, query)
    - ts_rank_cd(sections.text_tsv, tsquery)
    - Tenant filter enforced at SQL layer.

    Returns rows: (section_id, version_hash, url, text, page_type, rank).
    """
    config = (fts_config or os.getenv("FTS_LANG", "simple")).strip() or "simple"
    return execute_ac_bm25_retrieval(tenant_id, query, k, config)
