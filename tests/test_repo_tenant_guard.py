"""Unit tests: tenant-scoped query choke point. Repo raises immediately when tenant_id is None/empty."""

import pytest

from apps.api.services.repo import (
    TenantRequiredError,
    execute_ac_retrieval,
    get_evidence_by_ids,
    get_sections_by_query,
    insert_evidence,
    insert_raw_page,
    insert_sections,
)
from apps.api.services.tenant_guard import require_tenant_id, tenant_where


def test_repo_raises_on_none_or_empty_tenant() -> None:
    """Representative functions raise TenantRequiredError for None and empty tenant_id."""
    with pytest.raises(TenantRequiredError):
        get_sections_by_query(None, "q", 10)
    with pytest.raises(TenantRequiredError):
        get_sections_by_query("", "q", 10)
    with pytest.raises(TenantRequiredError):
        insert_raw_page(None, "http://x.com")


def test_retrieval_functions_raise_on_missing_tenant() -> None:
    """AC retrieval and evidence lookup raise before DB when tenant_id missing."""
    emb = "[" + ",".join("0.0" for _ in range(384)) + "]"  # valid pgvector dim
    with pytest.raises(TenantRequiredError):
        execute_ac_retrieval(None, emb, 5)
    with pytest.raises(TenantRequiredError):
        get_evidence_by_ids("", ["e1"])


def test_insert_raw_page_raises_on_empty_tenant() -> None:
    with pytest.raises(TenantRequiredError):
        insert_raw_page("", "http://example.com")


def test_insert_sections_raises_on_none_tenant() -> None:
    with pytest.raises(TenantRequiredError):
        insert_sections(None, 1, [{"section_id": "s1", "text": "x"}])


def test_insert_evidence_raises_on_whitespace_tenant() -> None:
    with pytest.raises(TenantRequiredError):
        insert_evidence("   ", [{"evidence_id": "e1", "section_id": "s1"}])


def test_require_tenant_id_raises_immediately_no_db() -> None:
    """require_tenant_id(tenant_id=None) raises before any DB access (choke point)."""
    with pytest.raises(TenantRequiredError):
        require_tenant_id(None)
    with pytest.raises(TenantRequiredError):
        require_tenant_id("")
    assert require_tenant_id("  ok  ") == "ok"


def test_tenant_where_produces_clause() -> None:
    """tenant_where(model, tenant_id) produces SQLAlchemy binary expression."""
    from apps.api.models.section import Section

    clause = tenant_where(Section, "t1")
    assert clause is not None
