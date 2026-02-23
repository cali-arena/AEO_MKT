"""Strict grounding validator. Validates claims against evidence before returning answer."""

import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from apps.api.schemas.responses import AnswerDraft, Claim
from apps.api.services.repo import insert_evidence
from apps.api.services.tenant_guard import require_tenant_id

try:
    from rapidfuzz import fuzz

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


@dataclass
class GroundingResult:
    """Result of validate_answer."""

    ok: bool
    validated_claims: list[Claim] = field(default_factory=list)
    dropped_claims: list[Claim] = field(default_factory=list)
    refusal_reason: str | None = None


DEFAULT_THRESHOLDS = {
    "min_claim_confidence": 0.0,
    "min_overlap": 0.0,
}


def _tokenize(text: str) -> set[str]:
    """Lowercase, split on non-word, return set of tokens."""
    return {w for w in re.split(r"\W+", text.lower()) if w}


def _jaccard_overlap(a: str, b: str) -> float:
    """Token Jaccard: |A ∩ B| / |A ∪ B|. Returns 0 for empty."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _fuzz_ratio(a: str, b: str) -> float:
    """RapidFuzz ratio 0-100 if available, else -1."""
    if not RAPIDFUZZ_AVAILABLE:
        return -1.0
    return float(fuzz.ratio(a, b))


def _overlap_score(claim_text: str, evidence_text: str) -> float:
    """
    Combine lexical Jaccard (primary) with optional rapidfuzz ratio.
    Returns Jaccard; if rapidfuzz available, uses max(jaccard, ratio/100).
    """
    j = _jaccard_overlap(claim_text, evidence_text)
    if RAPIDFUZZ_AVAILABLE:
        r = _fuzz_ratio(claim_text, evidence_text)
        if r >= 0:
            return max(j, r / 100.0)
    return j


def validate_answer(
    draft: AnswerDraft,
    evidence_map: dict[str, dict[str, Any]],
    thresholds: dict[str, float] | None = None,
    strict: bool = False,
) -> GroundingResult:
    """
    Validate answer draft against evidence.

    Hard rules:
    - Every claim must have non-empty evidence_ids
    - Every evidence_id must exist in evidence_map
    - Claim must pass overlap check vs concatenated quote_spans of its evidence_ids
    - claim.confidence >= min_claim_confidence
    - overlap >= min_overlap

    Returns {ok, validated_claims, dropped_claims, refusal_reason}.
    If strict=True and any claim fails, ok=False and refusal_reason set.
    """
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    min_confidence = th.get("min_claim_confidence", 0.0)
    min_overlap = th.get("min_overlap", 0.0)

    validated: list[Claim] = []
    dropped: list[Claim] = []

    for claim in draft.claims:
        # 1. Non-empty evidence_ids
        if not claim.evidence_ids:
            dropped.append(claim)
            if strict:
                return GroundingResult(
                    ok=False,
                    validated_claims=[],
                    dropped_claims=dropped,
                    refusal_reason="empty_evidence_ids",
                )
            continue

        # 2. Every evidence_id must exist in evidence_map
        for eid in claim.evidence_ids:
            if eid not in evidence_map:
                dropped.append(claim)
                if strict:
                    return GroundingResult(
                        ok=False,
                        validated_claims=[],
                        dropped_claims=dropped,
                        refusal_reason="invalid_evidence_id",
                    )
                break
        else:
            # 3. Overlap check
            quote_spans = []
            for eid in claim.evidence_ids:
                ev = evidence_map.get(eid, {})
                qs = ev.get("quote_span") or ev.get("quote") or ""
                quote_spans.append(qs)
            evidence_text = " ".join(quote_spans)

            overlap = _overlap_score(claim.text, evidence_text)
            if overlap < min_overlap:
                dropped.append(claim)
                if strict:
                    return GroundingResult(
                        ok=False,
                        validated_claims=[],
                        dropped_claims=dropped,
                        refusal_reason="low_overlap",
                    )
                continue

            # 4. Confidence threshold
            if claim.confidence < min_confidence:
                dropped.append(claim)
                if strict:
                    return GroundingResult(
                        ok=False,
                        validated_claims=[],
                        dropped_claims=dropped,
                        refusal_reason="low_confidence",
                    )
                continue

            validated.append(claim)

    return GroundingResult(
        ok=True,
        validated_claims=validated,
        dropped_claims=dropped,
        refusal_reason=None,
    )


def create_evidence_for_sections(
    tenant_id: str | None,
    sections: list[dict[str, Any]],
    default_url: str = "",
) -> list[str]:
    """
    Test compatibility helper. Creates one evidence row per section with deterministic bounds.

    Only allowed when ENV=test. Use build_evidence_map + evidence_records_for_insert in production.
    """
    if os.getenv("ENV") != "test":
        raise RuntimeError(
            "create_evidence_for_sections is a test helper only; use build_evidence_map and "
            "evidence_records_for_insert in production."
        )
    tenant_id = require_tenant_id(tenant_id)
    if not sections:
        return []

    records: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    for section in sections:
        text = (section.get("text") or "").strip()
        quote_span = text[:280]
        eid = str(uuid.uuid4())
        evidence_ids.append(eid)
        records.append(
            {
                "evidence_id": eid,
                "section_id": section["section_id"],
                "url": section.get("url") or default_url,
                "quote_span": quote_span,
                "start_char": 0,
                "end_char": len(quote_span),
                "version_hash": section.get("version_hash") or "",
            }
        )

    insert_evidence(tenant_id, records)
    return evidence_ids
