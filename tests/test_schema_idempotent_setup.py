"""Regression: schema reset + create is idempotent (no DuplicateTable when run twice)."""

import os

import pytest

from tests._db_bootstrap import postgres_reachable, run_test_db_schema_fixture


def _db_available() -> bool:
    url = os.environ.get("DATABASE_TEST_URL")
    if not url:
        return False
    return postgres_reachable(url)


def test_schema_setup_idempotent():
    """Run schema reset + create twice; assert no exception (no DuplicateTable)."""
    if not _db_available():
        pytest.skip("DATABASE_TEST_URL not set or Postgres not reachable")

    run_test_db_schema_fixture()
    run_test_db_schema_fixture()
    # No exception => idempotent
