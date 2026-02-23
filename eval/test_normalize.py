"""Unit tests for eval/normalize.py."""

import pytest

from eval.normalize import normalize_answer_response


def test_none_returns_defaults() -> None:
    out = normalize_answer_response(None)
    assert out["refused"] is False
    assert out["refusal_reason"] is None
    assert out["answer"] == ""
    assert out["claims"] == []
    assert out["citations"] == {}
    assert out["evidence_ids"] == []
    assert out["scores"] is None
    assert out["debug"] is None


def test_empty_dict_returns_defaults() -> None:
    out = normalize_answer_response({})
    assert out["refused"] is False
    assert out["answer"] == ""
    assert out["claims"] == []
    assert out["citations"] == {}
    assert out["evidence_ids"] == []
    assert out["scores"] is None
    assert out["debug"] is None


def test_refused_includes_refusal_reason() -> None:
    out = normalize_answer_response({"refused": True, "refusal_reason": "LOW_RETRIEVAL_CONFIDENCE"})
    assert out["refused"] is True
    assert out["refusal_reason"] == "LOW_RETRIEVAL_CONFIDENCE"


def test_refused_with_missing_reason_has_none() -> None:
    out = normalize_answer_response({"refused": True})
    assert out["refused"] is True
    assert out["refusal_reason"] is None


def test_success_shape() -> None:
    resp = {
        "refused": False,
        "answer": "We offer full packing.",
        "claims": [
            {"text": "We pack.", "evidence_ids": ["ev1"], "confidence": 0.9},
            {"text": "We move.", "evidence_ids": ["ev1", "ev2"], "confidence": 0.8},
        ],
        "citations": {"ev1": {"url": "https://x.com", "section_id": "s1", "quote_span": "pack"}},
        "debug": {"threshold": 0.35, "top_score": 0.72},
    }
    out = normalize_answer_response(resp)
    assert out["refused"] is False
    assert out["answer"] == "We offer full packing."
    assert len(out["claims"]) == 2
    assert out["citations"] == {"ev1": {"url": "https://x.com", "section_id": "s1", "quote_span": "pack"}}
    assert out["evidence_ids"] == ["ev1", "ev2"]
    assert out["scores"] == {"threshold": 0.35, "top_score": 0.72}
    assert out["debug"] == {"threshold": 0.35, "top_score": 0.72}


def test_malformed_claims_default_to_empty() -> None:
    out = normalize_answer_response({"claims": "not a list"})
    assert out["claims"] == []
    assert out["evidence_ids"] == []


def test_malformed_citations_default_to_empty_dict() -> None:
    out = normalize_answer_response({"citations": ["a", "b"]})
    assert out["citations"] == {}


def test_scores_only_from_valid_debug() -> None:
    out = normalize_answer_response({"debug": {"threshold": 0.35}})
    assert out["scores"] == {"threshold": 0.35}
    assert out["debug"] == {"threshold": 0.35}

    out2 = normalize_answer_response({"debug": "invalid"})
    assert out2["scores"] is None
    assert out2["debug"] is None


def test_evidence_ids_deduplicated() -> None:
    resp = {
        "claims": [
            {"text": "A", "evidence_ids": ["ev1", "ev2"], "confidence": 0.9},
            {"text": "B", "evidence_ids": ["ev1"], "confidence": 0.8},
        ],
    }
    out = normalize_answer_response(resp)
    assert out["evidence_ids"] == ["ev1", "ev2"]


def test_refused_string_coerced() -> None:
    out = normalize_answer_response({"refused": "true"})
    assert out["refused"] is True


def test_output_always_has_refusal_reason_key() -> None:
    out_success = normalize_answer_response({"refused": False, "answer": "Yes"})
    out_refused = normalize_answer_response({"refused": True, "refusal_reason": "no_evidence"})
    assert "refusal_reason" in out_success
    assert "refusal_reason" in out_refused
    assert out_success["refusal_reason"] is None
    assert out_refused["refusal_reason"] == "no_evidence"
