"""Rerank /retrieve/ac candidates with heuristics: page_type boosts, keyword proximity, exact phrase."""

import re
from typing import Any

# Page type boost order (higher = better). FAQ and service preferred over blog/unknown.
PAGE_TYPE_BOOST: dict[str, float] = {
    "faq": 0.3,
    "service": 0.25,
    "informational": 0.15,
    "blog": 0.05,
    "unknown": 0.0,
}
DEFAULT_PAGE_TYPE_BOOST = 0.0

# Exact phrase hit adds this to rerank score
EXACT_PHRASE_BOOST = 0.2

# Keyword proximity: 1 / (1 + min_gap) for gap in chars (closer = higher)
PROXIMITY_MAX_BOOST = 0.2


def _query_terms(query: str) -> list[str]:
    """Lowercase, split on non-word, filter empty."""
    return [w for w in re.split(r"\W+", query.lower()) if w]


def _page_type_score(page_type: str | None) -> float:
    """Boost for page_type. Higher for faq/service."""
    if not page_type:
        return DEFAULT_PAGE_TYPE_BOOST
    return PAGE_TYPE_BOOST.get(page_type.lower(), DEFAULT_PAGE_TYPE_BOOST)


def _exact_phrase_score(query: str, text: str) -> tuple[float, list[str]]:
    """1 if query as exact phrase in text else 0. Returns (score, reasons)."""
    if not query.strip() or not text:
        return 0.0, []
    q = query.strip().lower()
    t = text.lower()
    if q in t:
        return EXACT_PHRASE_BOOST, ["exact_phrase"]
    return 0.0, []


def _keyword_proximity_score(query: str, text: str) -> tuple[float, list[str]]:
    """
    Reward query terms appearing close together.
    Score = PROXIMITY_MAX_BOOST / (1 + min_gap_chars). Tie-break: earlier hit wins.
    """
    terms = _query_terms(query)
    if len(terms) < 2:
        return 0.0, []
    t = text.lower()
    positions: list[list[int]] = []
    for term in terms:
        starts = [m.start() for m in re.finditer(re.escape(term), t)]
        if not starts:
            return 0.0, []
        positions.append(starts)

    # Find minimal span that covers one occurrence of each term (greedy: earliest first)
    def min_span(acc: list[tuple[int, int]], rest: list[list[int]]) -> int | None:
        if not rest:
            if len(acc) < 2:
                return None
            lo = min(a[0] for a in acc)
            hi = max(a[1] for a in acc)
            return hi - lo
        best = None
        for pos in rest[0]:
            end = pos + 1
            span = min_span(acc + [(pos, end)], rest[1:])
            if span is not None and (best is None or span < best):
                best = span
        return best

    # Simple approach: for each first-term position, find nearest positions for others
    min_gap = None
    for p0 in positions[0]:
        cur_lo, cur_hi = p0, p0 + 1
        ok = True
        for i in range(1, len(positions)):
            best_d = None
            for p in positions[i]:
                lo = min(cur_lo, p)
                hi = max(cur_hi, p + 1)
                d = hi - lo
                if best_d is None or d < best_d:
                    best_d = d
                    nlo, nhi = lo, hi
            if best_d is None:
                ok = False
                break
            cur_lo, cur_hi = nlo, nhi
        if ok and cur_hi - cur_lo >= 0:
            g = cur_hi - cur_lo
            if min_gap is None or g < min_gap:
                min_gap = g

    if min_gap is None:
        return 0.0, []
    score = PROXIMITY_MAX_BOOST / (1.0 + float(min_gap))
    return round(score, 6), [f"proximity_gap={min_gap}"]


def rerank_sections(
    query: str,
    candidates: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    """
    Rerank candidates using page_type boosts, keyword proximity, exact phrase hits.

    Input candidates: section_id, merged_score, text (section text), page_type (optional).
    Output: same candidates + rerank_score, rerank_reasons, sorted by rerank_score desc (tie-break section_id).
    """
    enriched: list[dict[str, Any]] = []
    for c in candidates:
        section_id = c.get("section_id", "")
        merged = float(c.get("merged_score", 0.0))
        text = c.get("text") or ""
        page_type = c.get("page_type")

        reasons: list[str] = []

        pt_score = _page_type_score(page_type)
        if pt_score > 0:
            reasons.append(f"page_type:{page_type}")

        ex_score, ex_reasons = _exact_phrase_score(query, text)
        reasons.extend(ex_reasons)

        prox_score, prox_reasons = _keyword_proximity_score(query, text)
        reasons.extend(prox_reasons)

        rerank_score = round(merged + pt_score + ex_score + prox_score, 6)

        out = {**c, "rerank_score": rerank_score, "rerank_reasons": reasons}
        enriched.append(out)

    enriched.sort(key=lambda x: (-x["rerank_score"], x.get("section_id", "")))
    return enriched[:top_n]
