"""Tests for merge_scores helper: min-max normalization and hybrid merge."""

import pytest

from apps.api.services.retrieve import merge_scores


def test_merge_scores_empty_inputs():
    """Empty inputs return []."""
    assert merge_scores({}, {}) == []


def test_merge_scores_vec_only_bm25_zero():
    """Section in vector only has bm25_score=0."""
    result = merge_scores({"a": 1.0}, {})
    assert len(result) == 1
    assert result[0]["section_id"] == "a"
    assert result[0]["bm25_score"] == 0.0


def test_merge_scores_missing_channel_gets_zero():
    """Candidates missing a channel have that score = 0."""
    vec = {"sec_a": 0.9, "sec_b": 0.3}
    bm25 = {"sec_a": 0.5, "sec_c": 0.8}  # sec_b only in vec, sec_c only in bm25
    result = merge_scores(vec, bm25)

    by_sid = {r["section_id"]: r for r in result}
    assert "sec_a" in by_sid
    assert "sec_b" in by_sid
    assert "sec_c" in by_sid

    # sec_b: vector only -> bm25_score = 0
    assert by_sid["sec_b"]["bm25_score"] == 0.0
    assert by_sid["sec_b"]["vector_score"] >= 0

    # sec_c: bm25 only -> vector_score = 0
    assert by_sid["sec_c"]["vector_score"] == 0.0
    assert by_sid["sec_c"]["bm25_score"] >= 0


def test_merge_scores_normalization_and_weights():
    """merged = 0.6*vec_norm + 0.4*bm25_norm, both channels normalized to [0,1]."""
    vec = {"a": 0.0, "b": 1.0}
    bm25 = {"a": 0.0, "b": 1.0}
    result = merge_scores(vec, bm25, vec_weight=0.6, bm25_weight=0.4)

    by_sid = {r["section_id"]: r for r in result}
    # vec: min=0,max=1 -> a_norm=0, b_norm=1
    # bm25: min=0,max=1 -> a_norm=0, b_norm=1
    # a: merged = 0.6*0 + 0.4*0 = 0
    # b: merged = 0.6*1 + 0.4*1 = 1
    assert by_sid["a"]["vector_score"] == 0.0
    assert by_sid["a"]["bm25_score"] == 0.0
    assert by_sid["a"]["merged_score"] == 0.0
    assert by_sid["b"]["vector_score"] == 1.0
    assert by_sid["b"]["bm25_score"] == 1.0
    assert by_sid["b"]["merged_score"] == 1.0

    # Order: b first (higher merged)
    assert result[0]["section_id"] == "b"
    assert result[1]["section_id"] == "a"


def test_merge_scores_sorted_by_merged_then_section_id():
    """Results sorted by merged_score desc, then section_id for ties."""
    vec = {"x": 0.5, "y": 0.5, "z": 0.5}
    bm25 = {"x": 1.0, "y": 1.0, "z": 0.0}
    result = merge_scores(vec, bm25)

    # vec: all 0.5 -> norm 0 (min=max)
    # bm25: x,y=1, z=0 -> x_norm=1, y_norm=1, z_norm=0
    # x: 0.6*0 + 0.4*1 = 0.4
    # y: 0.6*0 + 0.4*1 = 0.4
    # z: 0.6*0 + 0.4*0 = 0
    # Order: x, y (tie 0.4, sorted by section_id), then z
    assert result[0]["section_id"] in ("x", "y")
    assert result[1]["section_id"] in ("x", "y")
    assert result[0]["section_id"] <= result[1]["section_id"]
    assert result[2]["section_id"] == "z"
