"""Smoke test: load tiny results.jsonl sample, verify metrics keys exist and rate values in [0,1]."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.metrics import _compute_metrics, _load_results

# Tiny sample: 2 refused, 2 answered (1 with citations)
SAMPLE_JSONL = """{"query_id":"s1","tenant_id":"t1","domain":"faq","query":"q1","refused":true,"answer":"","claims":[],"citations":null}
{"query_id":"s2","tenant_id":"t1","domain":"pricing","query":"q2","refused":true,"answer":"","claims":[]}
{"query_id":"s3","tenant_id":"t1","domain":"faq","query":"q3","refused":false,"answer":"Yes","claims":[{"text":"A","evidence_ids":["e1"],"confidence":0.9}],"citations":{"e1":{"url":"u","section_id":"s","quote_span":"x"}}}
{"query_id":"s4","tenant_id":"t1","domain":"pricing","query":"q4","refused":false,"answer":"No","claims":[],"citations":{}}
"""


@pytest.fixture
def sample_results_path():
    base = Path(__file__).resolve().parent / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    p = base / "results_metrics_smoke.jsonl"
    p.write_text(SAMPLE_JSONL, encoding="utf-8")
    try:
        yield p
    finally:
        p.unlink(missing_ok=True)


def test_metrics_keys_exist(sample_results_path):
    """Metrics output has required keys."""
    records = _load_results(sample_results_path)
    m = _compute_metrics(records)
    required = {
        "mention_answer_rate",
        "citation_rate",
        "attribution_accuracy_proxy",
        "hallucination_incidents",
        "hallucination_rate",
        "composite_visibility_index",
        "total_queries",
        "refused_count",
        "answered_count",
    }
    for k in required:
        assert k in m, f"missing key: {k}"


def test_rate_values_in_01(sample_results_path):
    """Rate metrics (and CVI/100) are in [0, 1]."""
    records = _load_results(sample_results_path)
    m = _compute_metrics(records)
    rate_keys = ["mention_answer_rate", "citation_rate", "attribution_accuracy_proxy", "hallucination_rate"]
    for k in rate_keys:
        v = m[k]
        assert 0 <= v <= 1, f"{k}={v} not in [0,1]"
    # composite_visibility_index is 0-100
    assert 0 <= m["composite_visibility_index"] <= 100
