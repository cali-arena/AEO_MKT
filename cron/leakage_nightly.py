#!/usr/bin/env python3
"""Leakage nightly: cross-tenant retrieval tests.

For each tenant T, runs "foreign" queries (from OTHER tenants) against /retrieve/ac as T.
If any query returns candidates => leakage => insert leakage_fail.
Else => insert leakage_pass.

Query source (Option A - simplest): reuse eval/queries_seed.jsonl.
  - For tenant T: take rows where tenant_id != T.
  - Run each query against POST /retrieve/ac with Authorization: Bearer tenant:T.
  - Assert candidates count == 0. If any > 0 => fail.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cron.config import config
from cron.logging import get_logger

logger = get_logger("leakage_nightly")


def _auth_header(tenant_id: str) -> str:
    token = os.getenv("EVAL_BEARER_TOKEN") or os.getenv("EVAL_API_KEY")
    if token:
        if "{tenant_id}" in token:
            token = token.format(tenant_id=tenant_id)
        return f"Bearer {token}"
    return f"Bearer tenant:{tenant_id}"


def _load_foreign_queries(tenant_id: str) -> list[dict[str, Any]]:
    """Load queries from OTHER tenants (eval/queries_seed.jsonl)."""
    project_root = Path(__file__).resolve().parent.parent
    seed_path = project_root / "eval" / "queries_seed.jsonl"
    if not seed_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with open(seed_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if str(obj.get("tenant_id", "")) != tenant_id:
                    rows.append(obj)
            except json.JSONDecodeError:
                continue
    return rows


def _call_retrieve_ac(
    session: requests.Session,
    base_url: str,
    tenant_id: str,
    query: str,
    k: int,
    timeout: float,
) -> tuple[list[dict[str, Any]], bool]:
    """POST /retrieve/ac. Returns (candidates, ok). ok=False if request failed (inconclusive)."""
    url = f"{base_url.rstrip('/')}/retrieve/ac"
    headers = {"Authorization": _auth_header(tenant_id), "Content-Type": "application/json"}
    body = {"query": query, "k": k}

    try:
        resp = session.post(url, json=body, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            logger.warning("retrieve/ac HTTP %s tenant=%s query=%s", resp.status_code, tenant_id, query[:50])
            return ([], False)
        data = resp.json()
        candidates = data.get("candidates") or []
        return (candidates, True)
    except Exception as e:
        logger.warning("retrieve/ac error tenant=%s query=%s: %s", tenant_id, query[:50], e)
        return ([], False)


def _run_tenant(tenant_id: str) -> tuple[bool, list[dict[str, Any]], bool]:
    """Run leakage check. Returns (passed, failures, all_ok). all_ok=False if any request failed (inconclusive)."""
    base_url = config.API_BASE.rstrip("/")
    timeout = 30.0
    k = 20

    foreign = _load_foreign_queries(tenant_id)
    if not foreign:
        logger.info("tenant=%s no foreign queries, skipping", tenant_id)
        return (True, [], True)

    failures: list[dict[str, Any]] = []
    all_ok = True
    with requests.Session() as session:
        for row in foreign:
            query = row.get("query", "") or row.get("query_text", "")
            if not query or not str(query).strip():
                continue
            owner = row.get("tenant_id", "?")
            candidates, ok = _call_retrieve_ac(session, base_url, tenant_id, str(query), k, timeout)
            if not ok:
                all_ok = False
            if candidates:
                urls = list({c.get("url", "") for c in candidates if c.get("url")})
                section_ids = [c.get("section_id", "") for c in candidates if c.get("section_id")]
                failures.append({
                    "query": query[:200],
                    "query_owner": owner,
                    "candidates_count": len(candidates),
                    "urls": urls[:10],
                    "section_ids": section_ids[:10],
                })
                logger.warning(
                    "tenant=%s LEAK query_owner=%s query=%s candidates=%s",
                    tenant_id,
                    owner,
                    query[:80],
                    len(candidates),
                )

    passed = len(failures) == 0
    return (passed, failures, all_ok)


def main() -> int:
    tenants = config.TENANTS
    if not tenants:
        logger.warning("TENANTS env empty, nothing to run")
        return 0

    logger.info("leakage_nightly start tenants=%s", tenants)
    any_failed = False

    try:
        from apps.api.services.repo import create_monitor_event
    except ImportError as e:
        logger.error("cannot import create_monitor_event: %s", e)
        return 1

    for tenant_id in tenants:
        passed, failures, all_ok = _run_tenant(tenant_id)

        if passed:
            if all_ok:
                foreign_count = len(_load_foreign_queries(tenant_id))
                create_monitor_event(
                    tenant_id=tenant_id,
                    event_type="leakage_pass",
                    severity="low",
                    details_json={
                        "foreign_queries_run": foreign_count,
                        "leaks": 0,
                    },
                )
                logger.info("tenant=%s PASS foreign_queries=%s", tenant_id, foreign_count)
            else:
                logger.warning("tenant=%s inconclusive (API errors), no event written", tenant_id)
                any_failed = True
        else:
            create_monitor_event(
                tenant_id=tenant_id,
                event_type="leakage_fail",
                severity="high",
                details_json={
                    "leak_count": len(failures),
                    "offending": failures,
                },
            )
            logger.error("tenant=%s FAIL leaks=%s", tenant_id, len(failures))
            any_failed = True

    logger.info("leakage_nightly done")
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
