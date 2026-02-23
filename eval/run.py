#!/usr/bin/env python3
"""Eval runner: run queries against /answer, prepare for DB insert.

CLI entrypoint. Loads queries, creates eval_run, evaluates each, prints summary.
Eval results insert is stubbed for now.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _get_git_sha() -> str | None:
    """Return current git SHA via subprocess, or GIT_SHA env. None if unavailable."""
    sha = os.getenv("GIT_SHA", "").strip()
    if sha:
        return sha
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parent.parent,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.strip() or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _auth_header(tenant_id: str) -> dict[str, str]:
    """Build Authorization header. Uses EVAL_BEARER_TOKEN or EVAL_API_KEY if set."""
    token = os.getenv("EVAL_BEARER_TOKEN") or os.getenv("EVAL_API_KEY")
    if token:
        if "{tenant_id}" in token:
            token = token.format(tenant_id=tenant_id)
        auth = f"Bearer {token}"
    else:
        auth = f"Bearer tenant:{tenant_id}"
    return {"Authorization": auth, "Content-Type": "application/json"}


def load_queries(path: Path) -> list[dict[str, Any]]:
    """Load queries from JSON file. Supports array or {queries: [...]}. Also supports JSONL."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Try as single JSON first
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "queries" in data:
            return data["queries"]
        raise ValueError("JSON must be an array or object with 'queries' key")
    except json.JSONDecodeError:
        pass

    # Fall back to JSONL
    queries: list[dict[str, Any]] = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            queries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return queries


def _compute_mention_ok(answer: str | None, expected_mentions: list[str]) -> bool:
    """True if any expected_mentions string appears in answer text. Strict substring, deterministic."""
    if answer is None or not expected_mentions:
        return False
    ans = str(answer)
    for s in expected_mentions:
        if isinstance(s, str) and s in ans:
            return True
    return False


def _compute_citation_ok(evidence_ids: list[str] | None) -> bool:
    """True if evidence_ids exists AND len > 0."""
    return bool(evidence_ids is not None and len(evidence_ids) > 0)


def _compute_attribution_ok(citations: dict[str, Any], expected_domain_pattern: str | None) -> bool:
    """True if any citation URL contains expected_domain_pattern. Strict substring, deterministic."""
    if not expected_domain_pattern or not isinstance(expected_domain_pattern, str):
        return False
    pattern = expected_domain_pattern.strip()
    if not pattern:
        return False
    for cite in citations.values():
        url: str | None = None
        if isinstance(cite, dict):
            url = cite.get("url")
        elif isinstance(cite, str):
            url = cite
        if isinstance(url, str) and pattern in url:
            return True
    return False


def _compute_hallucination_flag(refused: bool | None, citation_ok: bool) -> bool:
    """True if refused == False AND citation_ok == False (answered but no citations)."""
    return refused is False and not citation_ok


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Extract float safely. Returns default on unexpected schema."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _parse_answer_response(resp_data: dict[str, Any] | None) -> dict[str, Any]:
    """Parse /answer response fields. Fails gracefully on unexpected schema."""
    if not resp_data or not isinstance(resp_data, dict):
        return {
            "answer": None,
            "refused": None,
            "refusal_reason": None,
            "claims": [],
            "citations": {},
            "evidence_ids": [],
            "avg_confidence": 0.0,
        }
    claims = resp_data.get("claims")
    if not isinstance(claims, list):
        claims = []
    citations = resp_data.get("citations")
    if not isinstance(citations, dict):
        citations = {}
    evidence_ids: list[str] = []
    confidences: list[float] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        eids = c.get("evidence_ids")
        if isinstance(eids, list):
            evidence_ids.extend(str(x) for x in eids if x is not None)
        conf = c.get("confidence")
        if conf is not None:
            confidences.append(_safe_float(conf))
    evidence_ids = list(dict.fromkeys(evidence_ids))
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    debug = resp_data.get("debug")
    if isinstance(debug, dict) and avg_confidence == 0.0:
        top = debug.get("top_score")
        if top is not None:
            avg_confidence = _safe_float(top)
    answer = resp_data.get("answer")
    if not isinstance(answer, str):
        answer = str(answer) if answer is not None else None
    return {
        "answer": answer,
        "refused": resp_data.get("refused") if isinstance(resp_data.get("refused"), bool) else None,
        "refusal_reason": resp_data.get("refusal_reason") if isinstance(resp_data.get("refusal_reason"), (str, type(None))) else None,
        "claims": claims,
        "citations": citations,
        "evidence_ids": evidence_ids,
        "avg_confidence": avg_confidence,
    }


def evaluate_single_query(
    session: requests.Session,
    base_url: str,
    tenant_id: str,
    row: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """POST to /answer, parse response, return structured dict with raw + metrics placeholder.

    Handles HTTP errors, timeouts, and unexpected schema gracefully.
    """
    query = row.get("query", "")
    if not query or not str(query).strip():
        return {
            **row,
            "error": "missing query",
            "raw_response": None,
            "refused": None,
            "refusal_reason": None,
            "claims": [],
            "citations": {},
            "evidence_ids": [],
            "avg_confidence": 0.0,
            "metrics_flags": {
                "mention_ok": False,
                "citation_ok": False,
                "attribution_ok": False,
                "hallucination_flag": False,
            },
            "latency_ms": None,
        }

    url = f"{base_url.rstrip('/')}/answer"
    headers = _auth_header(tenant_id)
    body = {"query": query}

    latency_ms: float | None = None
    error: str | None = None
    resp_data: dict[str, Any] | None = None

    try:
        start = time.perf_counter()
        resp = session.post(url, json=body, headers=headers, timeout=timeout)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        if resp.status_code != 200:
            error = f"HTTP {resp.status_code}: {resp.text[:500]}"
            try:
                resp_data = resp.json() if resp.content else None
            except (json.JSONDecodeError, TypeError):
                resp_data = None
        else:
            try:
                resp_data = resp.json()
            except (json.JSONDecodeError, TypeError):
                error = "invalid JSON response"
                resp_data = None
    except requests.exceptions.Timeout as e:
        error = f"timeout: {e}"
        resp_data = None
    except requests.exceptions.RequestException as e:
        error = str(e)
        resp_data = None
    except Exception as e:
        error = f"unexpected error: {e}"
        resp_data = None

    parsed = _parse_answer_response(resp_data)
    citation_ok = _compute_citation_ok(parsed["evidence_ids"])
    expected_mentions = row.get("expected_mentions")
    if isinstance(expected_mentions, list):
        pass
    elif expected_mentions is not None:
        expected_mentions = [expected_mentions] if isinstance(expected_mentions, str) else []
    else:
        expected_mentions = []
    metrics_flags: dict[str, bool] = {
        "mention_ok": _compute_mention_ok(parsed["answer"], expected_mentions),
        "citation_ok": citation_ok,
        "attribution_ok": _compute_attribution_ok(
            parsed["citations"], row.get("expected_domain_pattern")
        ),
        "hallucination_flag": _compute_hallucination_flag(parsed["refused"], citation_ok),
    }

    result: dict[str, Any] = {
        **row,
        "raw_response": resp_data,
        "answer": parsed["answer"],
        "refused": parsed["refused"],
        "refusal_reason": parsed["refusal_reason"],
        "claims": parsed["claims"],
        "citations": parsed["citations"],
        "evidence_ids": parsed["evidence_ids"],
        "avg_confidence": parsed["avg_confidence"],
        "metrics_flags": metrics_flags,
        "latency_ms": latency_ms,
    }
    if error:
        result["error"] = error
    return result


def _extract_top_cited_urls(citations: dict[str, Any]) -> dict[str, str] | None:
    """Extract {evidence_id: url} from citations. None if empty."""
    if not citations or not isinstance(citations, dict):
        return None
    urls: dict[str, str] = {}
    for eid, cite in citations.items():
        if not isinstance(eid, str):
            continue
        url: str | None = None
        if isinstance(cite, dict):
            url = cite.get("url")
        elif isinstance(cite, str):
            url = cite
        if isinstance(url, str):
            urls[eid] = url
    return urls if urls else None


def _prepare_eval_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prepare list of eval_result rows for bulk insert. EvalResultCreate-shaped."""
    rows: list[dict[str, Any]] = []
    for r in results:
        citations = r.get("citations") or {}
        if not isinstance(citations, dict):
            citations = {}
        answer = r.get("answer") or ""
        answer_preview = (answer[:300] if answer else None) or None
        rows.append({
            "query_id": str(r.get("query_id") or ""),
            "domain": str(r.get("domain") or ""),
            "query_text": str(r.get("query") or ""),
            "refused": bool(r.get("refused") or False),
            "refusal_reason": r.get("refusal_reason") if r.get("refusal_reason") is not None else None,
            "mention_ok": (r.get("metrics_flags") or {}).get("mention_ok", False),
            "citation_ok": (r.get("metrics_flags") or {}).get("citation_ok", False),
            "attribution_ok": (r.get("metrics_flags") or {}).get("attribution_ok", False),
            "hallucination_flag": (r.get("metrics_flags") or {}).get("hallucination_flag", False),
            "evidence_count": len(r.get("evidence_ids") or []),
            "avg_confidence": float(r.get("avg_confidence") or 0.0),
            "top_cited_urls": _extract_top_cited_urls(citations),
            "answer_preview": answer_preview,
        })
    return rows


def run_eval(
    tenant_id: str,
    query_file: Path,
    base_url: str,
    timeout: float,
    crawl_policy_version: str,
    ac_version_hash: str,
    ec_version_hash: str,
    git_sha: str | None = None,
) -> tuple[int, UUID | None]:
    """Load queries, create eval_run, evaluate each, print summary. Returns (exit_code, run_id)."""
    queries = load_queries(query_file)
    if not queries:
        print("Error: no queries loaded", file=sys.stderr)
        return (1, None)

    # Print summary of loaded queries
    domains: dict[str, int] = {}
    for q in queries:
        d = q.get("domain") or "(none)"
        domains[d] = domains.get(d, 0) + 1
    print(f"Loaded {len(queries)} queries from {query_file}")
    print(f"Domains: {dict(sorted(domains.items()))}")

    run_id: UUID | None = None
    try:
        from apps.api.services.repo import create_eval_run

        run = create_eval_run(
            tenant_id=tenant_id,
            crawl_policy_version=crawl_policy_version,
            ac_version_hash=ac_version_hash,
            ec_version_hash=ec_version_hash,
            git_sha=git_sha,
        )
        run_id = run.id
        print(f"Eval run created: {run_id}")
    except Exception as e:
        print(f"Error creating eval_run: {e}", file=sys.stderr)
        return (1, None)

    results: list[dict[str, Any]] = []
    with requests.Session() as session:
        for i, row in enumerate(queries):
            rec = evaluate_single_query(session, base_url, tenant_id, row, timeout)
            results.append(rec)
            if rec.get("error"):
                print(f"  [{i+1}/{len(queries)}] {row.get('query_id', '?')}: {rec['error']}", file=sys.stderr)
            elif (i + 1) % 10 == 0 or i == len(queries) - 1:
                print(f"  [{i+1}/{len(queries)}] done")

    failure_count = sum(1 for r in results if r.get("error"))
    refused_count = sum(1 for r in results if r.get("refused") and not r.get("error"))
    print(f"\nDone. Total: {len(results)}, Failures: {failure_count}, Refused: {refused_count}")

    # Prepare eval_result rows and bulk insert
    eval_rows = _prepare_eval_results(results)
    inserted = 0
    if eval_rows and run_id is not None:
        try:
            from apps.api.schemas.eval import EvalResultCreate
            from apps.api.services.repo import insert_eval_results_bulk

            creates = [EvalResultCreate.model_validate(r) for r in eval_rows]
            inserted = insert_eval_results_bulk(tenant_id, run_id, creates)
        except Exception as e:
            print(f"Error inserting eval_results: {e}", file=sys.stderr)

    print(f"Run ID: {run_id}")
    print(f"Rows inserted: {inserted}")

    return (1 if failure_count else 0, run_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run eval against /answer, prepare for DB insert.")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID for API calls")
    parser.add_argument("--query-file", required=True, type=Path, help="Path to queries JSON (or JSONL)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--timeout", type=float, default=20.0, help="Request timeout seconds")
    parser.add_argument("--crawl-policy-version", default="run", help="Eval run metadata")
    parser.add_argument("--ac-version-hash", default="run", help="Eval run metadata")
    parser.add_argument("--ec-version-hash", default="run", help="Eval run metadata")
    parser.add_argument("--git-sha", help="Git SHA (default: from GIT_SHA env or git rev-parse HEAD)")
    args = parser.parse_args()

    if not args.query_file.exists():
        print(f"Error: query file not found: {args.query_file}", file=sys.stderr)
        return 1

    git_sha = args.git_sha.strip() if args.git_sha else _get_git_sha()
    return run_eval(
        tenant_id=args.tenant_id,
        query_file=args.query_file,
        base_url=args.base_url,
        timeout=args.timeout,
        crawl_policy_version=args.crawl_policy_version,
        ac_version_hash=args.ac_version_hash,
        ec_version_hash=args.ec_version_hash,
        git_sha=git_sha,
    )[0]


if __name__ == "__main__":
    sys.exit(main())
