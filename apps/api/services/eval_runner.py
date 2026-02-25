"""Run eval for a tenant (and optional domain): load queries, call /answer, persist eval_run + eval_result."""

import json
import os
from pathlib import Path
from typing import Any

import httpx

# Project root: apps/api/services -> api -> apps -> root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# Default queries when user adds a domain that has no rows in queries_seed.jsonl (eval runs 24/7 for it)
DEFAULT_QUERIES = [
    {"query_id": "default_1", "query": "What services do you offer?", "domain": ""},
    {"query_id": "default_2", "query": "How can I contact you?", "domain": ""},
    {"query_id": "default_3", "query": "What are your hours?", "domain": ""},
    {"query_id": "default_4", "query": "Do you have a FAQ or help page?", "domain": ""},
    {"query_id": "default_5", "query": "Where are you located?", "domain": ""},
]


def _load_queries(tenant_id: str, domain: str | None) -> list[dict[str, Any]]:
    """Load queries for tenant from eval/queries_seed.jsonl (and optional domain filter).
    When domain is set and seed has no rows for it, return default queries for that domain."""
    seed_path = PROJECT_ROOT / "eval" / "queries_seed.jsonl"
    if seed_path.exists():
        rows: list[dict[str, Any]] = []
        with open(seed_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if str(obj.get("tenant_id", "")) != tenant_id:
                        continue
                    if domain is not None and str(obj.get("domain", "")) != domain:
                        continue
                    rows.append(obj)
                except json.JSONDecodeError:
                    continue
        if rows or domain is None:
            return rows
    # Domain was requested but no seed queries: use defaults so eval can run 24/7 for this domain
    if domain:
        return [
            {**q, "tenant_id": tenant_id, "domain": domain}
            for q in DEFAULT_QUERIES
        ]
    return []


def _rec_to_eval_result_create(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Map harness-style result to EvalResultCreate fields. None to skip."""
    if rec.get("error"):
        return None
    from eval.harness import _rec_to_eval_result_create as harness_map

    return harness_map(rec)


def run_eval_sync(tenant_id: str, domain: str | None = None) -> dict[str, Any]:
    """
    Run eval for tenant (optional domain filter). Blocks.
    Returns dict: ok, run_id (str|None), count, error (str|None).
    """
    from apps.api.schemas.eval import EvalResultCreate
    from apps.api.services.repo import create_eval_run, insert_eval_results_bulk

    rows = _load_queries(tenant_id, domain)
    if not rows:
        return {"ok": True, "run_id": None, "count": 0, "error": None}

    base_url = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")
    timeout = 60.0
    auth_header = f"Bearer tenant:{tenant_id}"

    all_recs: list[dict[str, Any]] = []
    with httpx.Client(timeout=timeout) as client:
        for row in rows:
            query = row.get("query", "")
            if not query:
                all_recs.append({**row, "error": "missing query"})
                continue
            url = f"{base_url}/answer"
            headers = {"Authorization": auth_header, "Content-Type": "application/json"}
            body = {"query": query}
            try:
                resp = client.post(url, json=body, headers=headers)
                if resp.status_code != 200:
                    all_recs.append({**row, "error": f"HTTP {resp.status_code}"})
                    continue
                data = resp.json()
                debug = data.get("debug") or {}
                scores = {}
                if "threshold" in debug:
                    scores["threshold"] = debug["threshold"]
                if "top_score" in debug:
                    scores["top_score"] = debug["top_score"]
                rec = {
                    **row,
                    "refused": data.get("refused"),
                    "refusal_reason": data.get("refusal_reason"),
                    "answer": data.get("answer"),
                    "claims": data.get("claims"),
                    "citations": data.get("citations"),
                    "evidence_ids": _evidence_ids_from_claims(data.get("claims") or []),
                    "scores": scores,
                }
                all_recs.append(rec)
            except Exception as e:
                all_recs.append({**row, "error": str(e)})

    results_create: list[EvalResultCreate] = []
    for rec in all_recs:
        d = _rec_to_eval_result_create(rec)
        if d is not None:
            results_create.append(EvalResultCreate.model_validate(d))

    try:
        run = create_eval_run(
            tenant_id=tenant_id,
            crawl_policy_version="dashboard",
            ac_version_hash="dashboard",
            ec_version_hash="dashboard",
            git_sha=os.getenv("GIT_SHA"),
        )
        n = insert_eval_results_bulk(tenant_id, run.id, results_create) if results_create else 0
        return {"ok": True, "run_id": str(run.id), "count": n, "error": None}
    except Exception as e:
        return {"ok": False, "run_id": None, "count": 0, "error": str(e)}


def _evidence_ids_from_claims(claims: list[dict]) -> list[str]:
    out: list[str] = []
    for c in claims:
        out.extend(c.get("evidence_ids") or [])
    return list(dict.fromkeys(out))
