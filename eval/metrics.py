#!/usr/bin/env python3
"""Compute eval metrics from results.jsonl. Produces metrics_overall, metrics_by_domain, worst_queries."""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root on path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any

from eval.normalize import normalize_answer_response


# Composite Visibility Index weights
WEIGHT_ANSWER_RATE = 0.30
WEIGHT_CITATION_RATE = 0.30
WEIGHT_ATTRIBUTION_ACCURACY = 0.30
WEIGHT_HALLUCINATION_PENALTY = 0.10

# Worst queries: how many per category
WORST_TOP_N = 10


def _load_results(path: Path) -> list[dict[str, Any]]:
    """Load results.jsonl and normalize each record."""
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Skip rows with request-level error (no response)
            if raw.get("error"):
                continue
            resp = {
                "refused": raw.get("refused"),
                "refusal_reason": raw.get("refusal_reason"),
                "answer": raw.get("answer"),
                "claims": raw.get("claims"),
                "citations": raw.get("citations"),
                "evidence_ids": raw.get("evidence_ids"),
                "scores": raw.get("scores"),
                "debug": raw.get("debug"),
            }
            norm = normalize_answer_response(resp)
            record = {
                "query_id": raw.get("query_id"),
                "tenant_id": raw.get("tenant_id"),
                "domain": raw.get("domain"),
                "query": raw.get("query"),
                "notes": raw.get("notes"),
                **norm,
                "latency_ms": raw.get("latency_ms"),
            }
            records.append(record)
    return records


def _compute_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute all metrics for a set of records."""
    total = len(records)
    if total == 0:
        return {
            "total_queries": 0,
            "mention_answer_rate": 0.0,
            "citation_rate": 0.0,
            "attribution_accuracy_proxy": 0.0,
            "hallucination_incidents": 0,
            "hallucination_rate": 0.0,
            "composite_visibility_index": 0.0,
            "refused_count": 0,
            "answered_count": 0,
            "answered_with_citations_count": 0,
            "total_claims": 0,
            "supported_claims": 0,
        }

    refused_count = sum(1 for r in records if r.get("refused"))
    answered_count = total - refused_count

    # Mention/Answer Rate: % of queries that got an answer (not refused)
    mention_answer_rate = answered_count / total if total else 0.0

    # Citation Rate: of answered, % that have at least one citation
    answered_records = [r for r in records if not r.get("refused")]
    citations_raw = [r.get("citations") for r in answered_records]
    citations_list = [c for c in citations_raw if c and isinstance(c, dict) and len(c) > 0]
    answered_with_citations = len(citations_list)
    citation_rate = answered_with_citations / answered_count if answered_count else 0.0

    # Attribution Accuracy: supported_claims / total_claims
    total_claims = 0
    supported_claims = 0
    for r in answered_records:
        claims = r.get("claims") or []
        citations = r.get("citations") or {}
        if not isinstance(citations, dict):
            citations = {}
        for c in claims:
            if not isinstance(c, dict):
                continue
            total_claims += 1
            eids = c.get("evidence_ids") or []
            if not eids:
                continue
            if all(eid in citations for eid in eids):
                supported_claims += 1

    attribution_accuracy_proxy = supported_claims / total_claims if total_claims else 0.0

    # Hallucination: answered but (claim with empty evidence_ids) or (evidence_id not in citations)
    hallucination_incidents = 0
    for r in answered_records:
        claims = r.get("claims") or []
        citations = r.get("citations") or {}
        if not isinstance(citations, dict):
            citations = {}
        for c in claims:
            if not isinstance(c, dict):
                continue
            eids = c.get("evidence_ids") or []
            if not eids:
                hallucination_incidents += 1
                break
            if any(eid not in citations for eid in eids):
                hallucination_incidents += 1
                break

    hallucination_rate = hallucination_incidents / answered_count if answered_count else 0.0

    # Composite Visibility Index: weighted, 0-100
    cvi = (
        WEIGHT_ANSWER_RATE * mention_answer_rate
        + WEIGHT_CITATION_RATE * citation_rate
        + WEIGHT_ATTRIBUTION_ACCURACY * attribution_accuracy_proxy
        - WEIGHT_HALLUCINATION_PENALTY * hallucination_rate
    )
    cvi = max(0.0, min(1.0, cvi)) * 100

    return {
        "total_queries": total,
        "mention_answer_rate": round(mention_answer_rate, 4),
        "citation_rate": round(citation_rate, 4),
        "attribution_accuracy_proxy": round(attribution_accuracy_proxy, 4),
        "hallucination_incidents": hallucination_incidents,
        "hallucination_rate": round(hallucination_rate, 4),
        "composite_visibility_index": round(cvi, 2),
        "refused_count": refused_count,
        "answered_count": answered_count,
        "answered_with_citations_count": answered_with_citations,
        "total_claims": total_claims,
        "supported_claims": supported_claims,
    }


def _worst_queries(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build worst_queries: top refused, top low-score answered, top zero-citation answered."""
    # Deterministic: sort by query_id for ties
    def by_query_id(r: dict) -> str:
        return str(r.get("query_id") or "")

    refused = sorted(
        [r for r in records if r.get("refused")],
        key=lambda r: (by_query_id(r),),
    )[:WORST_TOP_N]

    answered = [r for r in records if not r.get("refused")]
    def _top_score(r: dict) -> float | None:
        return (r.get("scores") or {}).get("top_score")
    # Lowest scores first (worst); None treated as -1
    low_score = sorted(
        answered,
        key=lambda r: (_top_score(r) if _top_score(r) is not None else -1.0, by_query_id(r)),
    )[:WORST_TOP_N]

    zero_citation = sorted(
        [
            r
            for r in answered
            if not (r.get("citations") and isinstance(r.get("citations"), dict) and len(r.get("citations") or {}))
        ],
        key=lambda r: by_query_id(r),
    )[:WORST_TOP_N]

    def _summarize(rec: dict) -> dict[str, Any]:
        return {
            "query_id": rec.get("query_id"),
            "domain": rec.get("domain"),
            "query": rec.get("query")[:80] + ("..." if len(rec.get("query") or "") > 80 else ""),
            "refused": rec.get("refused"),
            "refusal_reason": rec.get("refusal_reason"),
            "top_score": (rec.get("scores") or {}).get("top_score"),
            "citation_count": len(rec.get("citations") or {}) if isinstance(rec.get("citations"), dict) else 0,
        }

    return {
        "top_refused": [_summarize(r) for r in refused],
        "top_low_score_answered": [_summarize(r) for r in low_score],
        "top_zero_citation_answered": [_summarize(r) for r in zero_citation],
    }


def _sorted_json(obj: Any) -> str:
    """JSON dump with sorted keys for deterministic output."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute metrics from results.jsonl")
    parser.add_argument("--in", dest="input_path", default="eval/out/results.jsonl", help="Input results.jsonl path")
    parser.add_argument("--out-dir", default="eval/out", help="Output directory for metrics JSON files")
    args = parser.parse_args()

    in_path = Path(args.input_path)
    if not in_path.exists():
        print(f"Error: input not found: {in_path}", file=sys.stderr)
        return 1

    records = _load_results(in_path)
    if not records:
        print("Warning: no valid records (all had errors or empty file)", file=sys.stderr)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_overall = _compute_metrics(records)
    with open(out_dir / "metrics_overall.json", "w", encoding="utf-8") as f:
        f.write(_sorted_json(metrics_overall))

    # By domain
    domains: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        d = r.get("domain") or "__unknown__"
        domains.setdefault(d, []).append(r)

    metrics_by_domain = {}
    for domain in sorted(domains.keys()):
        metrics_by_domain[domain] = _compute_metrics(domains[domain])
    with open(out_dir / "metrics_by_domain.json", "w", encoding="utf-8") as f:
        f.write(_sorted_json(metrics_by_domain))

    worst = _worst_queries(records)
    with open(out_dir / "worst_queries.json", "w", encoding="utf-8") as f:
        f.write(_sorted_json(worst))

    print(f"Wrote {out_dir / 'metrics_overall.json'}")
    print(f"Wrote {out_dir / 'metrics_by_domain.json'}")
    print(f"Wrote {out_dir / 'worst_queries.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
