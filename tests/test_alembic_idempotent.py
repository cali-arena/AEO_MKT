"""Regression: alembic upgrade head is idempotent (no exception when run twice)."""

import os

import pytest

from tests._db_bootstrap import get_test_schema_strategy, run_alembic_upgrade


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL_TEST") and not os.environ.get("DATABASE_TEST_URL"),
    reason="DATABASE_URL_TEST required for Alembic tests",
)
@pytest.mark.skipif(
    os.environ.get("TEST_SCHEMA_STRATEGY", "alembic").strip().lower() == "ensure_tables",
    reason="Alembic idempotency test only applies when TEST_SCHEMA_STRATEGY=alembic",
)
def test_alembic_upgrade_head_twice_no_exception():
    """Run alembic upgrade head twice in the same session; must not raise."""
    url = os.environ.get("DATABASE_URL_TEST") or os.environ.get("DATABASE_TEST_URL")
    run_alembic_upgrade(url)
    run_alembic_upgrade(url)  # second run must be idempotent, no DuplicateTable etc.
