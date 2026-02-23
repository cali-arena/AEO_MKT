"""Unit tests for grounding validator: each failure mode."""

from unittest.mock import patch

import pytest

from apps.api.schemas.responses import AnswerDraft, Claim
from apps.api.services.grounding import (
    GroundingResult,
    _jaccard_overlap,
    validate_answer,
)


def _claim(text: str, evidence_ids: list[str], confidence: float = 0.9) -> Claim:
    return Claim(text=text, evidence_ids=evidence_ids, confidence=confidence)


def _evidence(quote_span: str) -> dict:
    return {"quote_span": quote_span}


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_empty_evidence_ids_dropped() -> None:
    """Claim with empty evidence_ids is dropped."""
    draft = AnswerDraft(answer="A", claims=[_claim("Claim text", [])])
    evidence_map = {}
    r = validate_answer(draft, evidence_map)
    assert r.ok is True
    assert r.validated_claims == []
    assert len(r.dropped_claims) == 1
    assert r.dropped_claims[0].evidence_ids == []
    assert r.refusal_reason is None


def test_empty_evidence_ids_strict_refuses() -> None:
    """Strict mode: empty evidence_ids → refuse entire answer."""
    draft = AnswerDraft(answer="A", claims=[_claim("Claim text", [])])
    r = validate_answer(draft, {}, strict=True)
    assert r.ok is False
    assert r.refusal_reason == "empty_evidence_ids"
    assert r.validated_claims == []
    assert len(r.dropped_claims) == 1


def test_invalid_evidence_id_dropped() -> None:
    """Claim with evidence_id not in evidence_map is dropped."""
    draft = AnswerDraft(answer="A", claims=[_claim("Claim", ["e1"])])
    evidence_map = {}  # e1 not present
    r = validate_answer(draft, evidence_map)
    assert r.ok is True
    assert r.validated_claims == []
    assert len(r.dropped_claims) == 1


def test_invalid_evidence_id_strict_refuses() -> None:
    """Strict mode: invalid evidence_id → refuse."""
    draft = AnswerDraft(answer="A", claims=[_claim("Claim", ["e1"])])
    r = validate_answer(draft, {}, strict=True)
    assert r.ok is False
    assert r.refusal_reason == "invalid_evidence_id"


def test_low_overlap_dropped() -> None:
    """Claim with insufficient token overlap with evidence is dropped."""
    draft = AnswerDraft(answer="A", claims=[_claim("completely different words xyz", ["e1"])])
    evidence_map = {"e1": _evidence("storage moving relocation services")}
    r = validate_answer(draft, evidence_map, thresholds={"min_overlap": 0.5})
    assert r.ok is True
    assert r.validated_claims == []
    assert len(r.dropped_claims) == 1


def test_low_overlap_strict_refuses() -> None:
    """Strict mode: low overlap → refuse."""
    draft = AnswerDraft(answer="A", claims=[_claim("unrelated text", ["e1"])])
    evidence_map = {"e1": _evidence("storage and moving")}
    r = validate_answer(draft, evidence_map, thresholds={"min_overlap": 0.9}, strict=True)
    assert r.ok is False
    assert r.refusal_reason == "low_overlap"


def test_low_confidence_dropped() -> None:
    """Claim below min_claim_confidence is dropped."""
    draft = AnswerDraft(answer="A", claims=[_claim("storage moving", ["e1"], confidence=0.3)])
    evidence_map = {"e1": _evidence("storage and moving services")}
    r = validate_answer(draft, evidence_map, thresholds={"min_claim_confidence": 0.5})
    assert r.ok is True
    assert r.validated_claims == []
    assert len(r.dropped_claims) == 1


def test_low_confidence_strict_refuses() -> None:
    """Strict mode: low confidence → refuse."""
    draft = AnswerDraft(answer="A", claims=[_claim("storage moving", ["e1"], confidence=0.2)])
    evidence_map = {"e1": _evidence("storage moving")}
    r = validate_answer(draft, evidence_map, thresholds={"min_claim_confidence": 0.5}, strict=True)
    assert r.ok is False
    assert r.refusal_reason == "low_confidence"


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------


def test_valid_claims_pass() -> None:
    """Claims with valid evidence_ids and sufficient overlap/confidence pass."""
    draft = AnswerDraft(
        answer="We offer storage.",
        claims=[
            _claim("storage and moving services", ["e1"], confidence=0.9),
        ],
    )
    evidence_map = {"e1": _evidence("storage and moving services")}
    r = validate_answer(draft, evidence_map, thresholds={"min_overlap": 0.0, "min_claim_confidence": 0.5})
    assert r.ok is True
    assert len(r.validated_claims) == 1
    assert r.validated_claims[0].text == "storage and moving services"
    assert r.dropped_claims == []
    assert r.refusal_reason is None


def test_jaccard_overlap() -> None:
    """Jaccard token overlap behaves correctly."""
    assert _jaccard_overlap("a b c", "a b c") == 1.0
    assert _jaccard_overlap("a b", "c d") == 0.0
    assert _jaccard_overlap("a b c", "a b d") == 2 / 4  # {a,b} / {a,b,c,d}
    assert _jaccard_overlap("", "") == 1.0
    assert _jaccard_overlap("x", "") == 0.0


def test_overlap_uses_concatenated_quote_spans() -> None:
    """Overlap is computed against concatenated quote_spans of all evidence_ids."""
    draft = AnswerDraft(
        answer="A",
        claims=[_claim("storage moving", ["e1", "e2"])],
    )
    evidence_map = {
        "e1": _evidence("storage"),
        "e2": _evidence("moving"),
    }
    r = validate_answer(draft, evidence_map, thresholds={"min_overlap": 0.3})
    assert r.ok is True
    assert len(r.validated_claims) == 1


def test_create_evidence_for_sections_raises_when_env_not_test() -> None:
    """create_evidence_for_sections is test-only; raises RuntimeError when ENV != 'test'."""
    from apps.api.services.grounding import create_evidence_for_sections

    with pytest.raises(RuntimeError, match="test helper only"):
        with patch.dict("os.environ", {"ENV": "production"}, clear=False):
            create_evidence_for_sections("t", [{"section_id": "s1", "text": "x"}])
