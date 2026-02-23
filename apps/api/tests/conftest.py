"""Pytest fixtures for API tests."""

import os

import pytest

# Ensure tests can find apps when run from project root
os.environ.setdefault("PYTHONPATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
# Use deterministic embedding provider in tests (no network, no HuggingFace download)
os.environ.setdefault("ENV", "test")
os.environ["EMBED_PROVIDER"] = "deterministic"

# Deterministic policy for domain-gate tests (avoids flakiness from policy file path/caching)
DETERMINISTIC_POLICY = {
    "tenant_id": "test",
    "allowed_domains": ["coasttocoastmovers.com", "quote.unitedglobalvanline.com"],
    "quote_exclusions": {},
}


# Mirror: use shared marker from tests.conftest (single source of truth)
from tests.conftest import requires_db  # noqa: F401
