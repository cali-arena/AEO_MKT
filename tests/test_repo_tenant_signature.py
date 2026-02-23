"""Lint-like test: every public repo function that touches DB must have tenant_id as first parameter."""

import inspect

from apps.api.services import repo


def test_repo_public_functions_start_with_tenant_id() -> None:
    """All public functions defined in repo.py have tenant_id as first parameter."""
    for name, obj in inspect.getmembers(repo, inspect.isfunction):
        if name.startswith("_"):
            continue
        if getattr(obj, "__module__", "") != repo.__name__:
            continue  # skip imports (e.g. get_db)
        sig = inspect.signature(obj)
        params = list(sig.parameters)
        assert len(params) >= 1, f"repo.{name} has no parameters"
        assert params[0] == "tenant_id", (
            f"repo.{name} first param must be 'tenant_id', got {params[0]!r}"
        )
