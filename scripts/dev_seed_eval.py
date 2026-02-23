#!/usr/bin/env python3
"""Seed fake eval_run + eval_result rows for local dev. Tenant: coast2coast, domain: example.com.

Ensures eval_run/eval_result exist (creates only those tables to avoid conflicts with existing schema).
Use make seed or run with Postgres up.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_mkt")

from apps.api.db import engine
from apps.api.models.eval_run import EvalRun
from apps.api.models.eval_result import EvalResult
from apps.api.schemas.eval import EvalResultCreate
from apps.api.services.repo import (
    create_eval_run,
    get_eval_results,
    insert_eval_results_bulk,
    list_eval_runs,
)

TENANT = "coast2coast"
DOMAIN = "example.com"


def _ensure_schema() -> None:
    """Ensure eval_run and eval_result exist. Creates only these tables (avoids touching answer_cache, etc.)."""
    EvalRun.__table__.create(engine, checkfirst=True)
    EvalResult.__table__.create(engine, checkfirst=True)


def _make_result(query_id: str, query_text: str, **kw) -> EvalResultCreate:
    return EvalResultCreate(
        query_id=query_id,
        domain=DOMAIN,
        query_text=query_text,
        refused=kw.get("refused", False),
        refusal_reason=None,
        mention_ok=kw.get("mention_ok", True),
        citation_ok=kw.get("citation_ok", True),
        attribution_ok=kw.get("attribution_ok", True),
        hallucination_flag=kw.get("hallucination_flag", False),
        evidence_count=kw.get("evidence_count", 1),
        avg_confidence=kw.get("avg_confidence", 0.9),
        top_cited_urls=None,
        answer_preview="Preview",
    )


def main() -> int:
    _ensure_schema()

    run = create_eval_run(
        tenant_id=TENANT,
        crawl_policy_version="dev_seed",
        ac_version_hash="seed",
        ec_version_hash="seed",
        git_sha=None,
    )
    results = [
        _make_result("q1", "What services?"),
        _make_result("q2", "How to get a quote?"),
        _make_result("q3", "Contact info?"),
        _make_result("q4", "Do you ship nationwide?", mention_ok=False),
        _make_result("q5", "Hours of operation?"),
    ]
    n = insert_eval_results_bulk(TENANT, run.id, results)
    print(f"Seeded eval_run {run.id} with {n} eval_results for tenant={TENANT} domain={DOMAIN}")

    runs = list_eval_runs(TENANT, limit=5)
    assert len(runs) >= 1
    fetched = get_eval_results(TENANT, run.id, domain=DOMAIN)
    assert len(fetched) == 5
    print(f"Verify: list_eval_runs={len(runs)}, get_eval_results domain={DOMAIN}={len(fetched)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
