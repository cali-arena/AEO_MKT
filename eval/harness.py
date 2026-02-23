#!/usr/bin/env python3
"""Eval harness: run queries against /answer and save JSONL results.
Optional --write-db persists results to Postgres (eval_run + eval_result)."""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests

# Project root on path for apps.api imports when --write-db
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _auth_header(tenant_id: str) -> str:
    """Build Authorization header. Uses EVAL_BEARER_TOKEN or EVAL_API_KEY if set."""
    token = os.getenv("EVAL_BEARER_TOKEN") or os.getenv("EVAL_API_KEY")
    if token:
        if "{tenant_id}" in token:
            token = token.format(tenant_id=tenant_id)
        return f"Bearer {token}"
    return f"Bearer tenant:{tenant_id}"


def _call_answer(
    session: requests.Session,
    base_url: str,
    row: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """Call /answer for one query. Returns merged record for results.jsonl."""
    query = row.get("query", "")
    tenant_id = row.get("tenant_id", "")
    if not query:
        return {
            **row,
            "error": "missing query",
            "refused": None,
            "answer": None,
            "claims": None,
            "citations": None,
            "evidence_ids": None,
            "scores": None,
            "latency_ms": None,
            "run_meta": None,
        }

    url = f"{base_url.rstrip('/')}/answer"
    headers = {"Authorization": _auth_header(tenant_id), "Content-Type": "application/json"}
    body = {"query": query}

    latency_ms: float | None = None
    error: str | None = None
    resp_data: dict[str, Any] | None = None

    for attempt in range(2):
        try:
            start = time.perf_counter()
            resp = session.post(url, json=body, headers=headers, timeout=timeout)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)

            if 500 <= resp.status_code < 600 and attempt == 0:
                continue  # retry once on 5xx

            if resp.status_code != 200:
                error = f"HTTP {resp.status_code}: {resp.text[:500]}"
                try:
                    resp_data = resp.json()
                except Exception:
                    resp_data = None
                break

            resp_data = resp.json()
            error = None
            break
        except requests.exceptions.Timeout as e:
            error = f"timeout: {e}"
            break
        except Exception as e:
            error = str(e)
            break

    # Build result record
    evidence_ids: list[str] | None = None
    scores: dict[str, float] | None = None
    run_meta: dict[str, Any] | None = None

    if resp_data:
        claims = resp_data.get("claims") or []
        evidence_ids = []
        for c in claims:
            evidence_ids.extend(c.get("evidence_ids") or [])
        evidence_ids = list(dict.fromkeys(evidence_ids))  # dedupe

        debug = resp_data.get("debug")
        if debug:
            scores = {}
            if "threshold" in debug:
                scores["threshold"] = debug["threshold"]
            if "top_score" in debug:
                scores["top_score"] = debug["top_score"]

        run_meta = {}
        if "debug" in resp_data and resp_data["debug"]:
            run_meta["debug"] = resp_data["debug"]
        if not run_meta:
            run_meta = None

    # Pass through all request fields
    request_fields = {k: v for k, v in row.items()}
    return {
        **request_fields,
        "refused": resp_data.get("refused") if resp_data else None,
        "refusal_reason": resp_data.get("refusal_reason") if resp_data else None,
        "answer": resp_data.get("answer") if resp_data else None,
        "claims": resp_data.get("claims") if resp_data else None,
        "citations": resp_data.get("citations") if resp_data else None,
        "evidence_ids": evidence_ids,
        "scores": scores,
        "latency_ms": latency_ms,
        "run_meta": run_meta,
        **({"error": error} if error else {}),
    }


def _rec_to_eval_result_create(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Map harness result record to EvalResultCreate fields. Returns None to skip (e.g. error)."""
    if rec.get("error"):
        return None
    refused = rec.get("refused") or False
    refusal_reason = rec.get("refusal_reason")
    claims = rec.get("claims") or []
    citations = rec.get("citations") or {}
    if not isinstance(citations, dict):
        citations = {}
    evidence_ids = rec.get("evidence_ids") or []
    scores = rec.get("scores") or {}
    answer = rec.get("answer") or ""

    # mention_ok: got an answer (not refused)
    mention_ok = not refused
    # citation_ok: has at least one citation
    citation_ok = bool(citations and len(citations) > 0)
    # attribution_ok: all claims have evidence_ids and all are in citations
    total_claims = 0
    supported_claims = 0
    for c in claims:
        if not isinstance(c, dict):
            continue
        total_claims += 1
        eids = c.get("evidence_ids") or []
        if eids and all(eid in citations for eid in eids):
            supported_claims += 1
    attribution_ok = supported_claims == total_claims if total_claims else True
    # hallucination_flag: answered but claim with empty evidence_ids or evidence_id not in citations
    hallucination_flag = False
    if mention_ok:
        for c in claims:
            if not isinstance(c, dict):
                continue
            eids = c.get("evidence_ids") or []
            if not eids or any(eid not in citations for eid in eids):
                hallucination_flag = True
                break

    top_cited_urls: dict[str, str] | None = None
    if citations:
        top_cited_urls = {}
        for eid, cite in citations.items():
            if isinstance(cite, dict) and "url" in cite:
                top_cited_urls[str(eid)] = str(cite.get("url", ""))
            elif isinstance(cite, str):
                top_cited_urls[str(eid)] = cite

    return {
        "query_id": str(rec.get("query_id") or ""),
        "domain": str(rec.get("domain") or ""),
        "query_text": str(rec.get("query") or ""),
        "refused": refused,
        "refusal_reason": refusal_reason,
        "mention_ok": mention_ok,
        "citation_ok": citation_ok,
        "attribution_ok": attribution_ok,
        "hallucination_flag": hallucination_flag,
        "evidence_count": len(evidence_ids),
        "avg_confidence": float(scores.get("top_score", 0.0) or 0.0),
        "top_cited_urls": top_cited_urls,
        "answer_preview": (answer[:500] if answer else None),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval harness: call /answer for each query, save results.")
    parser.add_argument("--dataset", default="eval/queries_seed.jsonl", help="Input JSONL dataset path")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--out-dir", default="eval/out", help="Output directory for results.jsonl")
    parser.add_argument("--concurrency", type=int, default=1, help="Max concurrent requests")
    parser.add_argument("--timeout", type=float, default=60.0, help="Request timeout seconds")
    parser.add_argument("--write-db", action="store_true", help="Persist results to Postgres (eval_run + eval_result)")
    parser.add_argument("--tenant", help="Tenant ID for DB write (required when --write-db)")
    parser.add_argument("--crawl-policy-version", default="harness", help="Eval run metadata (default: harness)")
    parser.add_argument("--ac-version-hash", default="harness", help="Eval run metadata (default: harness)")
    parser.add_argument("--ec-version-hash", default="harness", help="Eval run metadata (default: harness)")
    parser.add_argument("--git-sha", help="Optional git SHA for eval run")
    args = parser.parse_args()

    if args.write_db and not (args.tenant or "").strip():
        print("Error: --tenant is required when --write-db", file=sys.stderr)
        return 1

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: dataset not found: {dataset_path}", file=sys.stderr)
        return 1

    rows: list[dict[str, Any]] = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: skip invalid line: {e}", file=sys.stderr)

    if not rows:
        print("Error: no valid rows in dataset", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results.jsonl"

    print(f"Running {len(rows)} queries against {args.base_url} (concurrency={args.concurrency}, timeout={args.timeout}s)")
    print(f"Output: {out_path}")
    if args.write_db:
        print(f"DB write: enabled (tenant={args.tenant})")

    failure_count = 0
    all_recs: list[dict[str, Any]] = []
    with open(out_path, "w", encoding="utf-8") as out_file:
        with requests.Session() as session:
            if args.concurrency <= 1:
                for row in rows:
                    rec = _call_answer(session, args.base_url, row, args.timeout)
                    if rec.get("error"):
                        failure_count += 1
                    all_recs.append(rec)
                    out_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out_file.flush()
            else:
                with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
                    futures = {ex.submit(_call_answer, session, args.base_url, row, args.timeout): row for row in rows}
                    for fut in as_completed(futures):
                        rec = fut.result()
                        if rec.get("error"):
                            failure_count += 1
                        all_recs.append(rec)
                        out_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        out_file.flush()

    print(f"Done. {len(rows)} results written. Failures: {failure_count}")

    if args.write_db and all_recs:
        try:
            from apps.api.schemas.eval import EvalResultCreate
            from apps.api.services.repo import create_eval_run, insert_eval_results_bulk

            run = create_eval_run(
                tenant_id=args.tenant,
                crawl_policy_version=args.crawl_policy_version,
                ac_version_hash=args.ac_version_hash,
                ec_version_hash=args.ec_version_hash,
                git_sha=args.git_sha or None,
            )
            results_create: list[EvalResultCreate] = []
            for rec in all_recs:
                d = _rec_to_eval_result_create(rec)
                if d is not None:
                    results_create.append(EvalResultCreate.model_validate(d))
            if results_create:
                n = insert_eval_results_bulk(args.tenant, run.id, results_create)
                print(f"DB: eval_run {run.id} created, {n} results inserted")
            else:
                print(f"DB: eval_run {run.id} created, 0 results (all had errors)")
        except Exception as e:
            print(f"DB write failed: {e}", file=sys.stderr)
            return 1

    return 1 if failure_count else 0


if __name__ == "__main__":
    sys.exit(main())
