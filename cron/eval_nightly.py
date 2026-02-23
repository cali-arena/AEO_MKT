#!/usr/bin/env python3
"""Eval nightly: run harness for each tenant, write results to DB. No JSONL output in production."""

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

# Project root on path for apps.api imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cron.config import config
from cron.logging import get_logger

logger = get_logger("eval_nightly")


def _call_answer(
    session: requests.Session,
    base_url: str,
    row: dict[str, Any],
    tenant_id: str,
    timeout: float,
) -> dict[str, Any]:
    """Call /answer for one query. Returns merged record."""
    from eval.harness import _call_answer as harness_call

    row_with_tenant = {**row, "tenant_id": tenant_id}
    return harness_call(session, base_url, row_with_tenant, timeout)


def _rec_to_eval_result_create(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Map harness result to EvalResultCreate fields. None to skip."""
    from eval.harness import _rec_to_eval_result_create as harness_map

    return harness_map(rec)


def _load_queries(tenant_id: str) -> list[dict[str, Any]]:
    """Load queries for tenant. Tries eval/queries_seed.jsonl, else eval/queries/*.json."""
    project_root = Path(__file__).resolve().parent.parent

    seed_path = project_root / "eval" / "queries_seed.jsonl"
    if seed_path.exists():
        rows: list[dict[str, Any]] = []
        with open(seed_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if str(obj.get("tenant_id", "")) == tenant_id:
                        rows.append(obj)
                except json.JSONDecodeError:
                    continue
        return rows

    queries_dir = project_root / "eval" / "queries"
    if queries_dir.is_dir():
        for p in sorted(queries_dir.glob("*.json")):
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [r for r in data if str(r.get("tenant_id", "")) == tenant_id]
            if isinstance(data, dict) and "queries" in data:
                return [r for r in data["queries"] if str(r.get("tenant_id", "")) == tenant_id]
            return []

    return []


def _run_tenant(tenant_id: str) -> tuple[bool, str | None, int, float, float]:
    """Run eval for one tenant. Returns (ok, run_id_str, count, refusal_rate, citation_rate)."""
    from apps.api.schemas.eval import EvalResultCreate
    from apps.api.services.repo import create_eval_run, insert_eval_results_bulk

    rows = _load_queries(tenant_id)
    if not rows:
        logger.warning("tenant=%s no queries found", tenant_id)
        return (True, None, 0, 0.0, 0.0)

    base_url = config.API_BASE.rstrip("/")
    timeout = 60.0
    all_recs: list[dict[str, Any]] = []

    with requests.Session() as session:
        for row in rows:
            rec = _call_answer(session, base_url, row, tenant_id, timeout)
            if rec.get("error"):
                logger.warning("tenant=%s query=%s error=%s", tenant_id, row.get("query_id"), rec.get("error"))
            all_recs.append(rec)

    results_create: list[EvalResultCreate] = []
    for rec in all_recs:
        d = _rec_to_eval_result_create(rec)
        if d is not None:
            results_create.append(EvalResultCreate.model_validate(d))

    all_failed = len(all_recs) > 0 and sum(1 for r in all_recs if r.get("error")) == len(all_recs)

    try:
        run = create_eval_run(
            tenant_id=tenant_id,
            crawl_policy_version="nightly",
            ac_version_hash="nightly",
            ec_version_hash="nightly",
            git_sha=os.getenv("GIT_SHA"),
        )
        n = insert_eval_results_bulk(tenant_id, run.id, results_create) if results_create else 0
    except Exception as e:
        logger.exception("tenant=%s DB write failed: %s", tenant_id, e)
        return (False, None, len(all_recs), 0.0, 0.0)

    refused = sum(1 for r in all_recs if r.get("refused") and not r.get("error"))
    citation_ok_count = sum(1 for r in results_create if r.citation_ok)
    total = len(results_create) if results_create else len(all_recs)
    refusal_rate = refused / total if total else 0.0
    citation_rate = citation_ok_count / total if total else 0.0

    ok = not all_failed
    return (ok, str(run.id), n, refusal_rate, citation_rate)


def main() -> int:
    tenants = config.TENANTS
    if not tenants:
        logger.warning("TENANTS env empty, nothing to run")
        return 0

    logger.info("eval_nightly start tenants=%s", tenants)
    any_failed = False

    for tenant_id in tenants:
        ok, run_id, count, refusal_rate, citation_rate = _run_tenant(tenant_id)
        logger.info(
            "tenant=%s run_id=%s count=%s refusal_rate=%.2f citation_rate=%.2f",
            tenant_id,
            run_id or "-",
            count,
            refusal_rate,
            citation_rate,
        )
        if not ok:
            any_failed = True

    logger.info("eval_nightly done")
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
