"""Regression: requires_db tests are skipped when DATABASE_TEST_URL is missing."""

import pytest


def test_requires_db_skipped_when_database_test_url_missing(monkeypatch):
    """When DATABASE_TEST_URL is unset, _db_available_for_tests returns False -> requires_db skips."""
    monkeypatch.delenv("DATABASE_TEST_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_TEST", raising=False)

    from tests.conftest import _db_available_for_tests

    assert _db_available_for_tests() is False
