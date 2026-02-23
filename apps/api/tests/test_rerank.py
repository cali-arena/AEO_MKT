"""Unit tests for rerank heuristics: page_type boosts, keyword proximity, exact phrase."""

import pytest

from apps.api.services.rerank import rerank_sections


def test_page_type_boosts_faq_highest() -> None:
    """FAQ gets highest boost, then service, then unknown."""
    q = "moving"
    c1 = {"section_id": "s1", "merged_score": 0.5, "text": "moving services", "page_type": "faq"}
    c2 = {"section_id": "s2", "merged_score": 0.5, "text": "moving services", "page_type": "service"}
    c3 = {"section_id": "s3", "merged_score": 0.5, "text": "moving services", "page_type": "unknown"}
    out = rerank_sections(q, [c1, c2, c3], top_n=3)
    assert [x["section_id"] for x in out] == ["s1", "s2", "s3"]
    assert out[0]["rerank_score"] > out[1]["rerank_score"] > out[2]["rerank_score"]
    assert "page_type:faq" in out[0]["rerank_reasons"]
    assert "page_type:service" in out[1]["rerank_reasons"]
    assert "page_type:unknown" not in out[2]["rerank_reasons"]


def test_page_type_none_gets_default_boost() -> None:
    """None or missing page_type gets DEFAULT_PAGE_TYPE_BOOST (0). Use query with no exact phrase."""
    q = "foo bar"
    c = {"section_id": "s1", "merged_score": 0.5, "text": "test content"}
    out = rerank_sections(q, [c], top_n=1)
    assert out[0]["rerank_score"] == 0.5
    assert not any("page_type:" in r for r in out[0]["rerank_reasons"])


def test_exact_phrase_boost() -> None:
    """Exact phrase hit adds EXACT_PHRASE_BOOST and reason."""
    q = "long distance moving"
    c_exact = {"section_id": "s1", "merged_score": 0.3, "text": "We offer long distance moving across the country."}
    c_partial = {"section_id": "s2", "merged_score": 0.3, "text": "We offer long and distance services. Moving too."}
    out = rerank_sections(q, [c_partial, c_exact], top_n=2)
    assert out[0]["section_id"] == "s1"
    assert "exact_phrase" in out[0]["rerank_reasons"]
    assert "exact_phrase" not in out[1]["rerank_reasons"]
    assert out[0]["rerank_score"] > out[1]["rerank_score"]


def test_keyword_proximity_closer_higher() -> None:
    """Closer keyword proximity yields higher rerank score."""
    q = "storage moving"
    c_close = {"section_id": "s1", "merged_score": 0.4, "text": "storage and moving services"}
    c_far = {"section_id": "s2", "merged_score": 0.4, "text": "storage services. Later we discuss moving."}
    out = rerank_sections(q, [c_far, c_close], top_n=2)
    assert out[0]["section_id"] == "s1"
    assert any("proximity_gap=" in r for r in out[0]["rerank_reasons"])
    assert out[0]["rerank_score"] > out[1]["rerank_score"]


def test_keyword_proximity_single_term_no_boost() -> None:
    """Single query term yields no proximity boost (only exact_phrase can apply)."""
    q = "relocation"
    c = {"section_id": "s1", "merged_score": 0.5, "text": "moving services"}
    out = rerank_sections(q, [c], top_n=1)
    assert out[0]["rerank_score"] == 0.5
    assert not any("proximity" in r for r in out[0]["rerank_reasons"])


def test_deterministic_tiebreak_by_section_id() -> None:
    """Equal rerank_score ties are broken by section_id."""
    q = "x y"
    c1 = {"section_id": "sec_b", "merged_score": 0.0, "text": "x y"}
    c2 = {"section_id": "sec_a", "merged_score": 0.0, "text": "x y"}
    out = rerank_sections(q, [c1, c2], top_n=2)
    assert [x["section_id"] for x in out] == ["sec_a", "sec_b"]


def test_top_n_limits_results() -> None:
    """rerank_sections returns at most top_n candidates."""
    candidates = [
        {"section_id": f"s{i}", "merged_score": 0.5, "text": "x y z"}
        for i in range(5)
    ]
    out = rerank_sections("x y", candidates, top_n=2)
    assert len(out) == 2


def test_empty_candidates_returns_empty() -> None:
    """Empty input returns empty output."""
    assert rerank_sections("query", [], top_n=5) == []


def test_output_includes_rerank_score_and_reasons() -> None:
    """Each output candidate has rerank_score and rerank_reasons."""
    c = {"section_id": "s1", "merged_score": 0.5, "text": "moving storage", "page_type": "faq"}
    out = rerank_sections("moving storage", [c], top_n=1)
    assert "rerank_score" in out[0]
    assert "rerank_reasons" in out[0]
    assert isinstance(out[0]["rerank_reasons"], list)
