"""AC/EC retrieval. Vector search via pgvector. DB access via repo only.
Tenant from auth only; client-provided tenant_id is never used. Zero cross-tenant results."""

import logging

import os

from apps.api.schemas.responses import (
    ECMention,
    RetrieveCandidate,
    RetrieveDebug,
    RetrieveDebugMerge,
    RetrieveDebugVector,
    RetrieveECCandidate,
    RetrieveECDebug,
    RetrieveECResponse,
    RetrieveResponse,
)
from apps.api.services.embedding_provider import embed_text
from apps.api.services.rerank import rerank_sections
from apps.api.services.repo import (
    execute_ac_retrieval,
    execute_ec_retrieval,
    get_entities_by_ids,
    get_entity_mentions_for_entities,
    get_urls_for_section_ids,
)
from apps.api.services.retrieve_bm25 import retrieve_ac_bm25
from apps.api.services.tenant_context import tenant_guard

logger = logging.getLogger(__name__)

SNIPPET_MAX = 240


def _embed_query(query: str) -> list[float]:
    """Embed a single query string via EmbeddingProvider (deterministic when ENV=test)."""
    return embed_text(query)


def _distance_to_score(distance: float) -> float:
    """Convert L2 distance to score: 1 / (1 + distance)."""
    return 1.0 / (1.0 + float(distance))


VECTOR_WEIGHT = 0.6
BM25_WEIGHT = 0.4
K_VEC = 50
K_BM25 = 50
NORM_EPSILON = 1e-9


def _min_max_normalize(scores: dict[str, float], epsilon: float = NORM_EPSILON) -> dict[str, float]:
    """Normalize scores to [0, 1] using min-max + epsilon. Missing keys stay at 0."""
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    denom = hi - lo + epsilon
    return {sid: (s - lo) / denom for sid, s in scores.items()}


def merge_scores(
    vec_by_section: dict[str, float],
    bm25_by_section: dict[str, float],
    vec_weight: float = VECTOR_WEIGHT,
    bm25_weight: float = BM25_WEIGHT,
    epsilon: float = NORM_EPSILON,
) -> list[dict]:
    """
    Merge vector and BM25 scores with min-max normalization.

    Normalizes each channel to [0, 1] per request (min-max + epsilon).
    merged = vec_weight * vec_norm + bm25_weight * bm25_norm.
    Candidates missing a channel have that score = 0.

    Returns list of {section_id, vector_score, bm25_score, merged_score} sorted by merged_score desc.
    """
    all_sections = set(vec_by_section) | set(bm25_by_section)
    if not all_sections:
        return []

    vec_norm = _min_max_normalize(vec_by_section, epsilon)
    bm25_norm = _min_max_normalize(bm25_by_section, epsilon)

    merged: list[dict] = []
    for sid in all_sections:
        v = vec_norm.get(sid, 0.0)
        b = bm25_norm.get(sid, 0.0)
        m = round(vec_weight * v + bm25_weight * b, 6)
        merged.append({
            "section_id": sid,
            "vector_score": round(v, 6),
            "bm25_score": round(b, 6),
            "merged_score": m,
        })

    merged.sort(key=lambda x: (-x["merged_score"], x["section_id"]))
    return merged


def retrieve_ac(
    tenant_id: str | None,
    query: str,
    k: int = 20,
) -> RetrieveResponse:
    """
    Hybrid retrieval for AC: vector + BM25 merged with 0.6*vec_norm + 0.4*bm25_norm.

    Fetches top k_vec (50) vector and top k_bm25 (50) BM25 candidates.
    Normalizes each channel to [0,1] (min-max + epsilon), merges, returns top k.
    """
    tenant_id = tenant_guard(tenant_id)
    fts_config = os.getenv("FTS_LANG", "simple").strip() or "simple"

    # Vector retrieval (top k_vec)
    query_embedding = _embed_query(query)
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    vec_rows = execute_ac_retrieval(tenant_id, embedding_str, K_VEC)

    vec_by_section: dict[str, float] = {}
    vec_meta: dict[str, tuple[str, str, str, str | None]] = {}
    for row in vec_rows:
        section_id, version_hash, url, text_val, page_type, distance = row
        score = _distance_to_score(distance)
        vec_by_section[section_id] = score
        vec_meta[section_id] = (version_hash or "", url or "", text_val or "", page_type)

    # BM25 retrieval (top k_bm25)
    bm25_rows = retrieve_ac_bm25(tenant_id, query, k=K_BM25, fts_config=fts_config)
    bm25_by_section: dict[str, float] = {}
    bm25_meta: dict[str, tuple[str, str, str, str | None]] = {}
    for row in bm25_rows:
        section_id, version_hash, url, text_val, page_type, rank = row
        bm25_by_section[section_id] = float(rank)
        bm25_meta[section_id] = (version_hash or "", url or "", text_val or "", page_type)

    # Merge with min-max normalization
    merged_list = merge_scores(vec_by_section, bm25_by_section)
    merged_top = merged_list[:k]

    # Rerank: page_type boosts, keyword proximity, exact phrase
    rerank_input = []
    for m in merged_top:
        meta = vec_meta.get(m["section_id"]) or bm25_meta.get(m["section_id"]) or ("", "", "", None)
        version_hash, url, text_val, page_type = meta
        rerank_input.append({
            "section_id": m["section_id"],
            "merged_score": m["merged_score"],
            "vector_score": m["vector_score"],
            "bm25_score": m["bm25_score"],
            "text": text_val or "",
            "page_type": page_type,
        })
    reranked = rerank_sections(query, rerank_input, top_n=k)

    all_sections = set(vec_by_section) | set(bm25_by_section)
    deduped_count = max(0, len(vec_rows) + len(bm25_rows) - len(all_sections))

    vector_debug = RetrieveDebugVector(
        requested_k=K_VEC,
        returned_k=len(vec_rows),
        min=min(vec_by_section.values()) if vec_by_section else 0.0,
        max=max(vec_by_section.values()) if vec_by_section else 0.0,
        top_scores=sorted(vec_by_section.values(), reverse=True)[:5] if vec_by_section else [],
    )
    bm25_debug = RetrieveDebugVector(
        requested_k=K_BM25,
        returned_k=len(bm25_rows),
        min=min(bm25_by_section.values()) if bm25_by_section else 0.0,
        max=max(bm25_by_section.values()) if bm25_by_section else 0.0,
        top_scores=sorted(bm25_by_section.values(), reverse=True)[:5] if bm25_by_section else [],
    )
    merge_debug = RetrieveDebugMerge(
        weights={"vector": VECTOR_WEIGHT, "bm25": BM25_WEIGHT},
        deduped_count=deduped_count,
        final_k=len(reranked),
    )

    candidates = []
    for r in reranked:
        meta = vec_meta.get(r["section_id"]) or bm25_meta.get(r["section_id"]) or ("", "", "", None)
        version_hash, url, text_val, _ = meta
        snippet = (text_val or "")[:SNIPPET_MAX]
        candidates.append(
            RetrieveCandidate(
                section_id=r["section_id"],
                merged_score=r["merged_score"],
                vector_score=r["vector_score"],
                bm25_score=r["bm25_score"],
                rerank_score=r["rerank_score"],
                rerank_reasons=r["rerank_reasons"],
                url=url,
                version_hash=version_hash,
                snippet=snippet,
            )
        )

    return RetrieveResponse(
        candidates=candidates,
        debug=RetrieveDebug(
            tenant_id=tenant_id,
            vector=vector_debug,
            bm25=bm25_debug,
            merge=merge_debug,
        ),
    )


def retrieve_ec(
    tenant_id: str | None,
    query: str,
    k: int = 20,
    n: int = 5,
) -> RetrieveECResponse:
    """
    Vector retrieval for EC. Search ec_embeddings by query embedding.
    Returns entity-level results with score and up to N mentions per entity
    (section_id, offsets, quote_span, url if resolvable).
    """
    tenant_id = tenant_guard(tenant_id)
    query_embedding = _embed_query(query)
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    rows = execute_ec_retrieval(tenant_id, embedding_str, k)
    if not rows:
        return RetrieveECResponse(
            entities=[],
            debug=RetrieveECDebug(tenant_id=tenant_id, vector=True, entity_count=0),
        )

    entity_ids = [r[0] for r in rows]
    entity_map = get_entities_by_ids(tenant_id, entity_ids)
    mentions_map = get_entity_mentions_for_entities(tenant_id, entity_ids, limit_per_entity=n)

    section_ids = set()
    for mentions in mentions_map.values():
        for m in mentions:
            section_ids.add(m["section_id"])
    urls = get_urls_for_section_ids(tenant_id, list(section_ids))

    entities_out = []
    for entity_id, distance in rows:
        ent = entity_map.get(entity_id, {"entity_id": entity_id, "canonical_name": "", "entity_type": ""})
        score = round(_distance_to_score(distance), 6)
        mentions_raw = mentions_map.get(entity_id, [])

        mentions = []
        for m in mentions_raw:
            url_val = urls.get(m["section_id"], "")
            mentions.append(
                ECMention(
                    section_id=m["section_id"],
                    start_offset=m["start_offset"],
                    end_offset=m["end_offset"],
                    quote_span=m["quote_span"],
                    url=url_val,
                )
            )

        entities_out.append(
            RetrieveECCandidate(
                entity_id=entity_id,
                score=score,
                canonical_name=ent["canonical_name"] or "",
                entity_type=ent["entity_type"] or "",
                mentions=mentions,
            )
        )

    return RetrieveECResponse(
        entities=entities_out,
        debug=RetrieveECDebug(tenant_id=tenant_id, vector=True, entity_count=len(entities_out)),
    )
