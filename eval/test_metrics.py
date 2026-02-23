"""Unit tests for eval/metrics.py."""

import json
import tempfile
from pathlib import Path

import pytest

# Ensure project root on path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.metrics import _compute_metrics, _load_results, _worst_queries, _sorted_json


def test_compute_metrics_empty() -> None:
    m = _compute_metrics([])
    assert m["total_queries"] == 0
    assert m["mention_answer_rate"] == 0.0
    assert m["citation_rate"] == 0.0
    assert m["attribution_accuracy_proxy"] == 0.0
    assert m["hallucination_incidents"] == 0
    assert m["composite_visibility_index"] == 0.0


def test_compute_metrics_all_refused() -> None:
    records = [
        {"refused": True, "answer": "", "claims": [], "citations": {}, "evidence_ids": []},
        {"refused": True, "answer": "", "claims": [], "citations": {}, "evidence_ids": []},
    ]
    m = _compute_metrics(records)
    assert m["total_queries"] == 2
    assert m["refused_count"] == 2
    assert m["answered_count"] == 0
    assert m["mention_answer_rate"] == 0.0
    assert m["citation_rate"] == 0.0
    assert m["hallucination_incidents"] == 0


def test_compute_metrics_mention_answer_rate() -> None:
    records = [
        {"refused": False, "answer": "Yes", "claims": [], "citations": {}, "evidence_ids": []},
        {"refused": True, "answer": "", "claims": [], "citations": {}, "evidence_ids": []},
    ]
    m = _compute_metrics(records)
    assert m["mention_answer_rate"] == 0.5
    assert m["answered_count"] == 1
    assert m["refused_count"] == 1


def test_compute_metrics_citation_rate() -> None:
    records = [
        {"refused": False, "answer": "A", "claims": [], "citations": {"e1": {}}, "evidence_ids": []},
        {"refused": False, "answer": "B", "claims": [], "citations": {}, "evidence_ids": []},
    ]
    m = _compute_metrics(records)
    assert m["citation_rate"] == 0.5
    assert m["answered_with_citations_count"] == 1


def test_compute_metrics_attribution_accuracy() -> None:
    records = [
        {
            "refused": False,
            "answer": "A",
            "claims": [
                {"text": "X", "evidence_ids": ["e1"], "confidence": 0.9},
                {"text": "Y", "evidence_ids": ["e2"], "confidence": 0.8},
            ],
            "citations": {"e1": {}, "e2": {}},
            "evidence_ids": ["e1", "e2"],
        },
    ]
    m = _compute_metrics(records)
    assert m["total_claims"] == 2
    assert m["supported_claims"] == 2
    assert m["attribution_accuracy_proxy"] == 1.0


def test_compute_metrics_attribution_partial() -> None:
    records = [
        {
            "refused": False,
            "answer": "A",
            "claims": [
                {"text": "X", "evidence_ids": ["e1"], "confidence": 0.9},
                {"text": "Y", "evidence_ids": ["e2"], "confidence": 0.8},
            ],
            "citations": {"e1": {}},
            "evidence_ids": ["e1", "e2"],
        },
    ]
    m = _compute_metrics(records)
    assert m["total_claims"] == 2
    assert m["supported_claims"] == 1
    assert m["attribution_accuracy_proxy"] == 0.5


def test_compute_metrics_hallucination_empty_evidence_ids() -> None:
    records = [
        {
            "refused": False,
            "answer": "A",
            "claims": [{"text": "X", "evidence_ids": [], "confidence": 0.9}],
            "citations": {},
            "evidence_ids": [],
        },
    ]
    m = _compute_metrics(records)
    assert m["hallucination_incidents"] == 1
    assert m["hallucination_rate"] == 1.0


def test_compute_metrics_hallucination_missing_citation() -> None:
    records = [
        {
            "refused": False,
            "answer": "A",
            "claims": [{"text": "X", "evidence_ids": ["e1"], "confidence": 0.9}],
            "citations": {},
            "evidence_ids": ["e1"],
        },
    ]
    m = _compute_metrics(records)
    assert m["hallucination_incidents"] == 1


def test_compute_metrics_composite_visibility() -> None:
    records = [
        {
            "refused": False,
            "answer": "A",
            "claims": [{"text": "X", "evidence_ids": ["e1"], "confidence": 0.9}],
            "citations": {"e1": {}},
            "evidence_ids": ["e1"],
        },
    ] * 2
    m = _compute_metrics(records)
    assert m["mention_answer_rate"] == 1.0
    assert m["citation_rate"] == 1.0
    assert m["attribution_accuracy_proxy"] == 1.0
    assert m["hallucination_incidents"] == 0
    assert m["composite_visibility_index"] >= 90


def test_worst_queries_deterministic_ordering() -> None:
    records = [
        {"query_id": "q2", "domain": "a", "query": "Q2", "refused": True, "scores": None, "citations": {}},
        {"query_id": "q1", "domain": "a", "query": "Q1", "refused": True, "scores": None, "citations": {}},
        {"query_id": "q3", "domain": "b", "query": "Q3", "refused": False, "scores": {"top_score": 0.2}, "citations": {}},
        {"query_id": "q4", "domain": "b", "query": "Q4", "refused": False, "scores": {"top_score": 0.5}, "citations": {"e1": {}}},
    ]
    worst = _worst_queries(records)
    assert [w["query_id"] for w in worst["top_refused"]] == ["q1", "q2"]
    assert [w["query_id"] for w in worst["top_low_score_answered"]] == ["q3", "q4"]
    assert [w["query_id"] for w in worst["top_zero_citation_answered"]] == ["q3"]


def test_load_results_normalizes_and_skips_errors() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write('{"query_id":"a","refused":true,"answer":"","claims":[]}\n')
        f.write('{"query_id":"b","error":"timeout"}\n')
        f.write('{"query_id":"c","refused":false,"answer":"X","claims":[]}\n')
        path = Path(f.name)
    try:
        records = _load_results(path)
        assert len(records) == 2
        assert records[0]["query_id"] == "a" and records[0]["refused"] is True
        assert records[1]["query_id"] == "c" and records[1]["refused"] is False
    finally:
        path.unlink()


def test_sorted_json_deterministic() -> None:
    obj1 = {"z": 1, "a": 2, "m": 3}
    obj2 = {"a": 2, "m": 3, "z": 1}
    assert _sorted_json(obj1) == _sorted_json(obj2)
    assert '"a"' in _sorted_json(obj1)
    assert _sorted_json(obj1).index('"a"') < _sorted_json(obj1).index('"m"')
    assert _sorted_json(obj1).index('"m"') < _sorted_json(obj1).index('"z"')
