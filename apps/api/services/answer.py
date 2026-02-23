"""Grounded answer service. Uses LLM + grounding validator. Caches answers by tenant+query+versions."""

import json
import logging
import os
from typing import Any

from apps.api.db import get_db
from apps.api.schemas.responses import AnswerDebug, AnswerDraft, AnswerResponse, Citation, Claim
from apps.api.services.cache import (
    cache_get,
    cache_set,
    compute_query_hash,
    make_cache_key,
    normalize_query,
)
from apps.api.services.evidence_map import build_evidence_map, evidence_records_for_insert
from apps.api.services.grounding import validate_answer
from apps.api.services.llm_provider import get_llm_provider
from apps.api.services.policy import load_policy
from apps.api.services.policy import crawl_policy_version as get_crawl_policy_version
from apps.api.services.repo import get_index_versions, get_section_by_id, insert_evidence
from apps.api.services.retrieve import retrieve_ac
from apps.api.services.span import select_quote_span

logger = logging.getLogger(__name__)

MAX_EVIDENCE_ITEMS = 5

# Prompt requires strict JSON output, no prose outside
ANSWER_PROMPT = """You are a grounded answer assistant. Given a query and evidence, return ONLY a valid JSON object.
Schema: {"answer": "<concise answer string>", "claims": [{"text": "<claim>", "evidence_ids": ["<id>", ...], "confidence": <0-1>}]}
Rules: Use ONLY evidence_ids from the provided evidence. Do not invent IDs. Return JSON only, no markdown or other text."""


def _extract_json(text: str) -> str | None:
    """Extract JSON object from LLM response. Handles wrapped markdown/code blocks."""
    s = text.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines)
    s = s.strip()
    start = s.find("{")
    end = s.rfind("}") + 1
    if start >= 0 and end > start:
        return s[start:end]
    return None


def _parse_answer_draft(raw: str) -> AnswerDraft | None:
    """Parse raw LLM response into AnswerDraft. Returns None on failure."""
    extracted = _extract_json(raw)
    if not extracted:
        return None
    try:
        data = json.loads(extracted)
        return AnswerDraft.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Answer draft parse failed: %s", e)
        return None


def _refuse(
    reason: str,
    citations: dict[str, Citation] | None = None,
    debug: AnswerDebug | None = None,
) -> AnswerResponse:
    return AnswerResponse(
        answer="",
        claims=[],
        citations=citations or {},
        debug=debug,
        refused=True,
        refusal_reason=reason,
    )


def _soft_mode() -> bool:
    """True = drop invalid claims and regenerate; False = strict, refuse on any failure. Default: strict."""
    return (os.getenv("ANSWER_SOFT_GROUNDING") or "false").lower() in ("true", "1", "yes")


def _min_merged_score() -> float:
    """Minimum top merged_score to proceed. From MIN_MERGED_SCORE env (default 0.35)."""
    return float(os.getenv("MIN_MERGED_SCORE", "0.35"))


def _grounding_thresholds() -> dict[str, float]:
    """Thresholds for grounding validator."""
    return {
        "min_claim_confidence": float(os.getenv("GROUNDING_MIN_CONFIDENCE", "0.0")),
        "min_overlap": float(os.getenv("GROUNDING_MIN_OVERLAP", "0.0")),
    }


def _answer_cache_ttl() -> int | None:
    """TTL in seconds for answer cache. From ANSWER_CACHE_TTL env; None = no expiry."""
    v = os.getenv("ANSWER_CACHE_TTL")
    if v is None or v == "":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def answer(query: str, tenant_id: str) -> AnswerResponse:
    """
    Retrieve candidates, create evidence, call LLM, run grounding validator.
    Uses cache keyed by tenant+query+ac_version_hash+ec_version_hash+crawl_policy_version.
    Skips cache when DB unavailable (e.g. tests without Postgres).
    """
    skip_cache = False
    try:
        ac_hash, ec_hash = get_index_versions(tenant_id)
    except Exception:
        ac_hash, ec_hash = "", ""
        skip_cache = True

    if not skip_cache:
        policy = load_policy()
        crawl_ver = get_crawl_policy_version(policy)
        norm_q = normalize_query(query)
        qhash = compute_query_hash(norm_q)
        key = make_cache_key(tenant_id, qhash, ac_hash, ec_hash, crawl_ver)

        try:
            with get_db() as session:
                cached = cache_get(session, key, tenant_id)
            if cached is not None:
                return AnswerResponse.model_validate(cached)
        except Exception:
            skip_cache = True

    result = _answer_impl(query, tenant_id)

    if not skip_cache:
        try:
            payload = result.model_dump(mode="json")
            with get_db() as session:
                cache_set(session, key, tenant_id, qhash, payload, ttl_seconds=_answer_cache_ttl())
        except Exception:
            pass

    return result


def _answer_impl(query: str, tenant_id: str) -> AnswerResponse:
    """
    Core answer logic: retrieve, create evidence, call LLM, run grounding validator.
    Strict: refuse on any claim failure. Soft: drop invalid claims, regenerate answer; refuse if none remain.
    """
    resp = retrieve_ac(tenant_id, query, k=5)
    candidates = resp.candidates

    if not candidates:
        return _refuse("no_evidence")

    top_score = candidates[0].merged_score
    threshold = _min_merged_score()
    if top_score < threshold:
        return _refuse(
            "LOW_RETRIEVAL_CONFIDENCE",
            citations={},
            debug=AnswerDebug(threshold=threshold, top_score=top_score),
        )

    retrieval_results: list[dict[str, Any]] = []
    for c in candidates[:MAX_EVIDENCE_ITEMS]:
        section = get_section_by_id(tenant_id, c.section_id)
        if not section:
            logger.warning("Section not found section_id=%s tenant_id=%s", c.section_id, tenant_id)
            return _refuse("evidence_error")

        section_text = section.get("text") or ""
        quote_span, start_char, end_char = select_quote_span(section_text, query)
        retrieval_results.append({
            "section_id": c.section_id,
            "url": c.url,
            "quote_span": quote_span,
            "start_char": start_char,
            "end_char": end_char,
            "version_hash": section.get("version_hash"),
        })

    evidence_map = build_evidence_map(tenant_id, retrieval_results)
    evidence_records = evidence_records_for_insert(tenant_id, retrieval_results)
    try:
        insert_evidence(tenant_id, evidence_records)
    except Exception as e:
        logger.warning("Evidence insert failed: %s", e)
        return _refuse("evidence_error")

    evidence_items = [
        {"evidence_id": eid, "quote_span": ev["quote_span"], "section_id": ev["section_id"]}
        for eid, ev in evidence_map.items()
    ]

    provider = get_llm_provider()
    evidence_str = json.dumps(evidence_items, ensure_ascii=False)
    prompt = f"{ANSWER_PROMPT}\n\nQuery: {query}\n\nEvidence: {evidence_str}\n\nJSON:"
    raw_response = provider.generate(prompt, evidence_items)

    draft = _parse_answer_draft(raw_response)
    if draft is None:
        return _refuse("llm_parse_error", _build_citations(evidence_map))

    strict = not _soft_mode()
    result = validate_answer(draft, evidence_map, thresholds=_grounding_thresholds(), strict=strict)

    if not result.ok:
        return _refuse(result.refusal_reason or "grounding_failed", _build_citations(evidence_map))

    validated = result.validated_claims

    if not validated:
        return _refuse("no_validated_claims", _build_citations(evidence_map))

    # Regenerate answer from validated claims only
    answer_text = " ".join(c.text for c in validated)[:400].strip()
    if len(answer_text) >= 400:
        answer_text = answer_text[:397].rstrip() + "..."

    claims_out = [Claim(text=c.text, evidence_ids=c.evidence_ids, confidence=c.confidence) for c in validated]
    citations_out = _build_citations(evidence_map)

    return AnswerResponse(
        answer=answer_text,
        claims=claims_out,
        citations=citations_out,
        debug=AnswerDebug(threshold=threshold, top_score=top_score),
        refused=False,
        refusal_reason=None,
    )


def _build_citations(evidence_map: dict[str, dict[str, Any]]) -> dict[str, Citation]:
    """Build citations dict from evidence_map."""
    return {
        eid: Citation(url=ev["url"], section_id=ev["section_id"], quote_span=ev["quote_span"])
        for eid, ev in evidence_map.items()
    }
