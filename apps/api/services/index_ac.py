"""AC indexing into pgvector. DB access via repo only."""

import logging
from typing import Any

from apps.api.services.embedding_provider import embed_texts
from apps.api.services.repo import _assert_tenant, get_existing_ac_section_ids, insert_ac_embeddings

logger = logging.getLogger(__name__)


def embed_sections(texts: list[str]) -> list[list[float]]:
    """Compute embeddings for section texts via EmbeddingProvider (deterministic when ENV=test)."""
    return embed_texts(texts)


def index_ac(
    tenant_id: str | None,
    sections: list[dict[str, Any]],
) -> int:
    """
    Embed section texts and upsert into ac_embeddings.
    sections: [{section_id, text, version_hash, url}]
    Skips sections already indexed for (tenant_id, section_id).
    Returns count of sections indexed.
    """
    _assert_tenant(tenant_id)
    if not sections:
        return 0

    existing = get_existing_ac_section_ids(tenant_id)
    to_index = [s for s in sections if s["section_id"] not in existing]
    if not to_index:
        logger.info("index_ac tenant_id=%s all %d sections already indexed", tenant_id, len(sections))
        return 0

    texts = [s["text"] or "" for s in to_index]
    vectors = embed_sections(texts)
    if len(vectors) != len(to_index):
        raise RuntimeError("embed_sections returned wrong length")

    records = [
        {"section_id": s["section_id"], "embedding": v}
        for s, v in zip(to_index, vectors)
    ]
    insert_ac_embeddings(tenant_id, records)

    logger.info("index_ac tenant_id=%s indexed %d sections", tenant_id, len(records))
    return len(records)
