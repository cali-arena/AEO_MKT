"""Regression: alembic strategy never calls ensure_tables(). Enforces 'never mix' rule."""

import os

import pytest


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL_TEST") and not os.environ.get("DATABASE_TEST_URL"),
    reason="DATABASE_URL_TEST required for schema setup test",
)
def test_alembic_strategy_does_not_call_ensure_tables(monkeypatch):
    """With TEST_SCHEMA_STRATEGY=alembic, session setup must never call ensure_tables()."""
    monkeypatch.setenv("TEST_SCHEMA_STRATEGY", "alembic")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("PYTEST_RUNNING", "1")
    url = os.environ.get("DATABASE_URL_TEST") or os.environ.get("DATABASE_TEST_URL")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL_TEST", url)

    called = []

    def fail_if_called(*args, **kwargs):
        called.append(1)
        raise AssertionError(
            "ensure_tables() must not be called when TEST_SCHEMA_STRATEGY=alembic. "
            "Schema must come from alembic upgrade head only."
        )

    monkeypatch.setattr("apps.api.db.ensure_tables", fail_if_called)

    from tests._db_bootstrap import run_test_db_schema_fixture

    run_test_db_schema_fixture()
    assert len(called) == 0, "ensure_tables() was invoked during alembic strategy setup"
