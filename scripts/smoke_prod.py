#!/usr/bin/env python3
"""Smoke test for production shape. Verifies /health, /metrics/latest, eval_run, leakage monitor_event.

Run with: make smoke (or python scripts/smoke_prod.py)
Requires: API running. Start API with EMBED_PROVIDER=deterministic (or ENV=test) to avoid HuggingFace.
"""

import os
import subprocess
import sys
from pathlib import Path

import requests

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API_BASE = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")
TENANT = "smoke_smoke"
AUTH_HEADER = f"Bearer tenant:{TENANT}"


def _get(path: str) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", headers={"Authorization": AUTH_HEADER}, timeout=30)


def _ok(resp: requests.Response) -> bool:
    return resp.status_code == 200


def main() -> int:
    failures: list[str] = []

    # 1. GET /health => ok true
    print("1. GET /health ...")
    try:
        r = requests.get(f"{API_BASE}/health", timeout=10)
        if not _ok(r):
            failures.append(f"/health => {r.status_code}")
        else:
            data = r.json()
            if not data.get("ok"):
                failures.append("/health => ok not True")
            else:
                print("   ok")
    except Exception as e:
        failures.append(f"/health => {e}")
        print(f"   FAIL: {e}")
        return 1

    # 2. GET /metrics/latest with auth (may 404 if no runs yet)
    print("2. GET /metrics/latest (pre-eval) ...")
    try:
        r = _get("/metrics/latest")
        if r.status_code not in (200, 404):
            failures.append(f"/metrics/latest => {r.status_code}")
        print(f"   {r.status_code}")
    except Exception as e:
        failures.append(f"/metrics/latest => {e}")
        print(f"   FAIL: {e}")
        return 1

    # 3. Run tiny eval (5 queries), confirm eval_run inserted
    print("3. Eval (5 queries) -> DB ...")
    dataset = ROOT / "scripts" / "smoke_queries.jsonl"
    if not dataset.exists():
        failures.append("scripts/smoke_queries.jsonl not found")
        return 1
    try:
        env = os.environ.copy()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "eval.harness",
                "--dataset",
                str(dataset),
                "--base-url",
                API_BASE,
                "--write-db",
                "--tenant",
                TENANT,
                "--crawl-policy-version",
                "smoke",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            failures.append(f"eval harness exit {result.returncode}: {result.stderr[:500]}")
            print(f"   FAIL: {result.stderr[:300]}")
        else:
            print("   ok")
    except subprocess.TimeoutExpired:
        failures.append("eval harness timeout")
        return 1
    except Exception as e:
        failures.append(f"eval => {e}")
        print(f"   FAIL: {e}")
        return 1

    # 4. GET /metrics/latest => 200 (eval_run exists)
    print("4. GET /metrics/latest (post-eval) ...")
    try:
        r = _get("/metrics/latest")
        if not _ok(r):
            failures.append(f"/metrics/latest post-eval => {r.status_code}")
            return 1
        print("   200 ok")
    except Exception as e:
        failures.append(f"/metrics/latest => {e}")
        return 1

    # 5. Run leakage once
    print("5. Leakage ...")
    try:
        env = os.environ.copy()
        env["TENANTS"] = TENANT
        env["API_BASE"] = API_BASE
        result = subprocess.run(
            [sys.executable, "-m", "cron.leakage_nightly"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        # leakage exits 1 on fail (leaks found), 0 on pass
        print(f"   exit {result.returncode}")
    except subprocess.TimeoutExpired:
        failures.append("leakage timeout")
        return 1
    except Exception as e:
        failures.append(f"leakage => {e}")
        return 1

    # 6. GET /monitor/leakage/latest => 200, monitor_event exists
    print("6. GET /monitor/leakage/latest ...")
    try:
        r = _get("/monitor/leakage/latest")
        if not _ok(r):
            failures.append(f"/monitor/leakage/latest => {r.status_code}")
            return 1
        data = r.json()
        if "last_checked_at" not in data:
            failures.append("/monitor/leakage/latest missing last_checked_at")
        print("   200 ok")
    except Exception as e:
        failures.append(f"/monitor/leakage/latest => {e}")
        return 1

    if failures:
        print("\nFAILURES:", failures)
        return 1
    print("\nSmoke passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
