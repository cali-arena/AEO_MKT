"""Regression: mixing guard raises when both Alembic and ensure_tables would run."""

import os

import pytest

from tests._db_bootstrap import assert_not_mixed_schema_setup, get_test_schema_strategy


def test_assert_not_mixed_raises_after_both_invoked():
    """After fixture runs one path, attempting the other raises RuntimeError."""
    # Reset module state for this test (simulate fresh session)
    import tests._db_bootstrap as mod
    mod._alembic_invoked = True
    mod._ensure_tables_invoked = True

    with pytest.raises(RuntimeError) as exc:
        assert_not_mixed_schema_setup("alembic")
    assert "Mixed schema setup" in str(exc.value)
    assert "TEST_SCHEMA_STRATEGY" in str(exc.value)


def test_assert_not_mixed_raises_alembic_after_ensure_tables():
    """Trying alembic after ensure_tables ran raises."""
    import tests._db_bootstrap as mod
    mod._alembic_invoked = False
    mod._ensure_tables_invoked = True

    with pytest.raises(RuntimeError) as exc:
        assert_not_mixed_schema_setup("alembic")
    assert "Cannot run Alembic" in str(exc.value)
    assert "ensure_tables path already ran" in str(exc.value)


def test_assert_not_mixed_raises_ensure_tables_after_alembic():
    """Trying ensure_tables after alembic ran raises."""
    import tests._db_bootstrap as mod
    mod._alembic_invoked = True
    mod._ensure_tables_invoked = False

    with pytest.raises(RuntimeError) as exc:
        assert_not_mixed_schema_setup("ensure_tables")
    assert "Cannot run ensure_tables" in str(exc.value)
    assert "Alembic path already ran" in str(exc.value)


def test_strategy_default_is_alembic():
    """When TEST_SCHEMA_STRATEGY is unset, default is alembic."""
    prev = os.environ.pop("TEST_SCHEMA_STRATEGY", None)
    try:
        assert get_test_schema_strategy() == "alembic"
    finally:
        if prev is not None:
            os.environ["TEST_SCHEMA_STRATEGY"] = prev


def test_strategy_ensure_tables():
    """TEST_SCHEMA_STRATEGY=ensure_tables is accepted."""
    os.environ["TEST_SCHEMA_STRATEGY"] = "ensure_tables"
    try:
        assert get_test_schema_strategy() == "ensure_tables"
    finally:
        os.environ.pop("TEST_SCHEMA_STRATEGY", None)
