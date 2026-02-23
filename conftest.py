"""Root conftest: test DB bootstrap and env apply to ALL test paths (tests/, apps/api/tests/, eval/)."""

import os

import pytest

# Ensure ENV=test for deterministic embeddings and policy
os.environ.setdefault("ENV", "test")
os.environ.setdefault("PYTEST_RUNNING", "1")
os.environ.setdefault("EMBED_PROVIDER", "deterministic")

# 1) DB override detection: DATABASE_TEST_URL only
DATABASE_TEST_URL = os.getenv("DATABASE_TEST_URL")

from tests._db_bootstrap import (
    ensure_test_db_guard,
    postgres_reachable,
    run_test_db_schema_fixture,
)

# Run guard at conftest load; fails early if wrong DB (when test URL is set)
if DATABASE_TEST_URL:
    ensure_test_db_guard()


def _db_available_for_schema() -> bool:
    """True if DATABASE_TEST_URL is set and Postgres is reachable."""
    if not DATABASE_TEST_URL:
        return False
    return postgres_reachable(DATABASE_TEST_URL)


@pytest.fixture(scope="session", autouse=True)
def test_db_schema():
    """Reset test DB schema at session start. Only runs if DATABASE_TEST_URL is set and reachable.
    Drops schema public CASCADE, recreates it, applies schema via SCHEMA_AUTHORITY.
    Safety: db name must contain '_test' or ALLOW_TEST_DB_RESET=true.
    DB tests are skipped via @pytest.mark.requires_db when not configured."""
    if not _db_available_for_schema():
        return
    run_test_db_schema_fixture()
