"""Regression: when ENV=test, ensure_tables() must not call Base.metadata.create_all()."""

import os

import pytest


def test_ensure_tables_no_op_when_env_test(monkeypatch):
    """With ENV=test and strategy=alembic, ensure_tables() does not call create_all."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("PYTEST_RUNNING", "1")
    monkeypatch.setenv("TEST_SCHEMA_STRATEGY", "alembic")

    from apps.api.models import Base
    from apps.api.db import ensure_tables

    raised = []

    def fail_if_called(*args, **kwargs):
        raised.append(1)
        raise AssertionError("create_all must not be called when ENV=test")

    monkeypatch.setattr(Base.metadata, "create_all", fail_if_called)
    ensure_tables()
    assert len(raised) == 0, "ensure_tables() should no-op when strategy=alembic"
