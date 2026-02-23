"""Pytest fixtures for root-level tests (crawl rules, leakage, etc)."""

import os

import pytest

# Ensure ENV=test (root conftest also does this; redundant but safe for tests/ only runs)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("PYTEST_RUNNING", "1")
os.environ.setdefault("EMBED_PROVIDER", "deterministic")

# Re-export for tests that import run_alembic_upgrade from conftest (e.g. test_alembic_idempotent)
from tests._db_bootstrap import (
    postgres_reachable,
    run_alembic_upgrade,
    run_test_db_schema_fixture,
)  # noqa: F401


@pytest.fixture(scope="session", autouse=True)
def test_db_schema():
    """Reset test DB schema at session start. Only runs if DATABASE_TEST_URL is set and reachable.
    Drops schema public CASCADE, recreates it, then applies schema via SCHEMA_AUTHORITY (alembic or ensure_tables).
    Safety: db name must contain '_test' or ALLOW_TEST_DB_RESET=true."""
    if not _db_available_for_tests():
        return
    run_test_db_schema_fixture()


def _db_available_for_tests() -> bool:
    """True if DATABASE_TEST_URL is set and Postgres is reachable (short timeout)."""
    url = os.environ.get("DATABASE_TEST_URL")
    if not url:
        return False
    return postgres_reachable(url)


# Marker for DB tests: skip if DATABASE_TEST_URL not set or Postgres not reachable
requires_db = pytest.mark.skipif(
    not _db_available_for_tests(),
    reason="DATABASE_TEST_URL not set or Postgres not reachable",
)
