"""Repository layer. All functions require tenant_id as first argument; guard raises if None/empty.

RULE: Repo is the ONLY place allowed to run DB reads/writes (session.execute, get_db).
All tenant-scoped queries MUST use tenant_filters (select_*_for_tenant / tenant_where).

GUARD: Every function MUST call require_tenant_id(tenant_id) before any DB access.
"""

import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Float, Integer, case, cast, delete, func, or_, select, text

from apps.api.db import get_db
from apps.api.models.ac_embedding import ACEmbedding
from apps.api.models.ec_embedding import ECEmbedding
from apps.api.models.domain_index_state import DomainIndexState
from apps.api.models.entity import Entity
from apps.api.models.eval_domain import EvalDomain
from apps.api.models.eval_result import EvalResult
from apps.api.models.eval_run import EvalRun
from apps.api.models.evidence import Evidence
from apps.api.models.monitor_event import MonitorEvent
from apps.api.models.raw_page import RawPage
from apps.api.models.ec_version import ECVersion
from apps.api.models.entity_mention import EntityMention
from apps.api.models.relation import Relation
from apps.api.models.section import Section
from apps.api.models.tenant_index_version import TenantIndexVersion
logger = logging.getLogger(__name__)

from apps.api.repositories.tenant_filters import (
    select_ac_embedding_for_tenant,
    select_ec_embedding_for_tenant,
    select_entity_for_tenant,
    select_entity_mention_for_tenant,
    select_eval_result_for_tenant,
    select_eval_run_for_tenant,
    select_evidence_for_tenant,
    select_monitor_event_for_tenant,
    select_raw_page_for_tenant,
    select_section_for_tenant,
    tenant_where,
)
from apps.api.schemas.eval import EvalResultCreate
from apps.api.services.tenant_guard import TenantRequiredError, require_tenant_id


def _assert_tenant(tenant_id: str | None) -> None:
    """Legacy guard; prefer require_tenant_id. Raises if tenant_id missing."""
    require_tenant_id(tenant_id)


def get_existing_ac_section_ids(
    tenant_id: str | None,
    domain: str | None = None,
) -> set[str]:
    """Return section_ids already indexed in ac_embeddings. Filter by tenant_id and optionally domain."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_ac_embedding_for_tenant(tenant_id).with_only_columns(ACEmbedding.section_id)
    if domain is not None:
        stmt = stmt.where(ACEmbedding.domain == domain)
    with get_db() as session:
        rows = session.execute(stmt).all()
        return {r[0] for r in rows}


def insert_ac_embeddings(
    tenant_id: str | None,
    records: Sequence[dict[str, Any]],
) -> None:
    """Bulk insert ac_embeddings. Each dict: section_id, embedding, domain."""
    tenant_id = require_tenant_id(tenant_id)
    if not records:
        return
    with get_db() as session:
        objs = [
            ACEmbedding(
                tenant_id=tenant_id,
                domain=r["domain"],
                section_id=r["section_id"],
                embedding=r["embedding"],
            )
            for r in records
        ]
        session.add_all(objs)


def execute_ac_bm25_retrieval(
    tenant_id: str | None,
    query: str,
    k: int,
    fts_config: str = "simple",
    domain: str | None = None,
) -> list[tuple[Any, ...]]:
    """
    BM25-style FTS retrieval on sections.text_tsv using websearch_to_tsquery and ts_rank_cd.
    Returns rows (section_id, version_hash, url, text, page_type, rank).
    Filter by tenant_id and optionally domain. Returns [] if query empty.
    """
    tenant_id = require_tenant_id(tenant_id)
    if not query or not query.strip():
        return []
    q = query.strip()
    domain_clause = " AND s.domain = :domain" if domain is not None else ""
    sql = text("""
        SELECT s.section_id, s.version_hash, COALESCE(r.canonical_url, r.url) AS url, s.text,
               COALESCE(s.page_type, r.page_type) AS page_type,
               ts_rank_cd(s.text_tsv, websearch_to_tsquery(:config, :query))::float AS rank
        FROM sections s
        JOIN raw_page r ON s.raw_page_id = r.id AND r.tenant_id = s.tenant_id
        WHERE s.tenant_id = :tenant_id AND r.tenant_id = :tenant_id
          AND s.text_tsv @@ websearch_to_tsquery(:config, :query)
          """ + domain_clause + """
        ORDER BY rank DESC, s.section_id ASC
        LIMIT :k
    """)
    params: dict[str, Any] = {"tenant_id": tenant_id, "query": q, "config": fts_config, "k": k}
    if domain is not None:
        params["domain"] = domain
    with get_db() as session:
        return session.execute(sql, params).fetchall()


def execute_ac_retrieval(
    tenant_id: str | None,
    embedding_str: str,
    k: int,
    domain: str | None = None,
) -> list[tuple[Any, ...]]:
    """
    Run vector retrieval SQL. Joins ac_embeddings, sections, raw_page.
    Filter by tenant_id and optionally domain. Returns rows (section_id, version_hash, url, text, page_type, distance).
    """
    tenant_id = require_tenant_id(tenant_id)
    domain_clause = " AND ae.domain = :domain" if domain is not None else ""
    sql = text("""
        SELECT s.section_id, s.version_hash, r.url, s.text,
               COALESCE(s.page_type, r.page_type) AS page_type,
               ae.embedding <-> CAST(:embedding AS vector) AS distance
        FROM ac_embeddings ae
        JOIN sections s ON ae.tenant_id = s.tenant_id AND ae.section_id = s.section_id
        JOIN raw_page r ON s.raw_page_id = r.id AND r.tenant_id = s.tenant_id
        WHERE ae.tenant_id = :tenant_id AND s.tenant_id = :tenant_id AND r.tenant_id = :tenant_id
          """ + domain_clause + """
        ORDER BY ae.embedding <-> CAST(:embedding AS vector)
        LIMIT :k
    """)
    params: dict[str, Any] = {"tenant_id": tenant_id, "embedding": embedding_str, "k": k}
    if domain is not None:
        params["domain"] = domain
    with get_db() as session:
        return session.execute(sql, params).fetchall()


def get_raw_page_metadata(
    tenant_id: str | None,
    raw_page_id: int,
) -> dict[str, str | int | None]:
    """Return {domain, page_type, crawl_policy_version, version} for raw_page, or empty dict if not found."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select_raw_page_for_tenant(tenant_id)
        .where(RawPage.id == raw_page_id)
        .with_only_columns(RawPage.domain, RawPage.page_type, RawPage.crawl_policy_version, RawPage.version)
    )
    with get_db() as session:
        row = session.execute(stmt).first()
        if not row:
            return {}
        return {"domain": row[0], "page_type": row[1], "crawl_policy_version": row[2], "version": row[3]}


def get_raw_page_url(tenant_id: str | None, raw_page_id: int) -> str | None:
    """Return url for raw_page, or None if not found."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select_raw_page_for_tenant(tenant_id)
        .where(RawPage.id == raw_page_id)
        .with_only_columns(RawPage.url, RawPage.canonical_url)
    )
    with get_db() as session:
        row = session.execute(stmt).first()
        if not row:
            return None
        return row[1] or row[0]


def get_sections_by_raw_page_id(
    tenant_id: str | None,
    raw_page_id: int,
) -> list[dict[str, Any]]:
    """Return section records for a raw_page. Always filter by tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_section_for_tenant(tenant_id).where(Section.raw_page_id == raw_page_id)
    with get_db() as session:
        rows = session.scalars(stmt).all()
        return [
            {
                "section_id": r.section_id,
                "heading_path": r.heading_path,
                "text": r.text,
                "start_char": r.start_char,
                "end_char": r.end_char,
                "version_hash": r.version_hash,
                "domain": r.domain,
                "page_type": r.page_type,
                "crawl_policy_version": r.crawl_policy_version,
            }
            for r in rows
        ]


def get_artifact_counts_for_raw_page(
    tenant_id: str | None,
    raw_page_id: int,
) -> tuple[int, int, int]:
    """
    Return (sections_count, ac_embeddings_count, ec_embeddings_count) for a raw_page.
    Used to detect missing artifacts when raw_page content is unchanged.
    Strict: tenant_id + raw_page_id for sections; ac/ec scoped to those section_ids.
    """
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        sections_stmt = (
            select(func.count(Section.id))
            .select_from(Section)
            .where(tenant_where(Section, tenant_id), Section.raw_page_id == raw_page_id)
        )
        sections_count = session.execute(sections_stmt).scalar() or 0
        if sections_count == 0:
            return (0, 0, 0)
        section_ids_stmt = (
            select(Section.section_id)
            .where(tenant_where(Section, tenant_id), Section.raw_page_id == raw_page_id)
        )
        section_ids = [r[0] for r in session.execute(section_ids_stmt).all()]
        if not section_ids:
            return (0, 0, 0)
        ac_stmt = (
            select(func.count(ACEmbedding.id))
            .select_from(ACEmbedding)
            .where(tenant_where(ACEmbedding, tenant_id), ACEmbedding.section_id.in_(section_ids))
        )
        ac_count = session.execute(ac_stmt).scalar() or 0
        entity_ids_stmt = (
            select(Entity.entity_id)
            .where(tenant_where(Entity, tenant_id), Entity.section_id.in_(section_ids))
        )
        entity_ids = [r[0] for r in session.execute(entity_ids_stmt).all()]
        ec_count = 0
        if entity_ids:
            ec_stmt = (
                select(func.count(ECEmbedding.id))
                .select_from(ECEmbedding)
                .where(tenant_where(ECEmbedding, tenant_id), ECEmbedding.entity_id.in_(entity_ids))
            )
            ec_count = session.execute(ec_stmt).scalar() or 0
    return (sections_count, ac_count, ec_count)


def delete_ac_embeddings_for_section_ids(
    tenant_id: str | None,
    section_ids: Sequence[str],
) -> int:
    """Delete ac_embeddings for given section_ids. Returns count deleted. Enforces tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    if not section_ids:
        return 0
    stmt = delete(ACEmbedding).where(
        tenant_where(ACEmbedding, tenant_id),
        ACEmbedding.section_id.in_(list(section_ids)),
    )
    with get_db() as session:
        result = session.execute(stmt)
        return result.rowcount or 0


def delete_ec_embeddings_for_section_ids(
    tenant_id: str | None,
    section_ids: Sequence[str],
) -> int:
    """Delete ec_embeddings for entities whose section_id is in section_ids. Returns count deleted."""
    tenant_id = require_tenant_id(tenant_id)
    if not section_ids:
        return 0
    entity_ids_subq = (
        select(Entity.entity_id)
        .where(tenant_where(Entity, tenant_id), Entity.section_id.in_(list(section_ids)))
    )
    stmt = delete(ECEmbedding).where(
        tenant_where(ECEmbedding, tenant_id),
        ECEmbedding.entity_id.in_(entity_ids_subq),
    )
    with get_db() as session:
        result = session.execute(stmt)
        return result.rowcount or 0


def get_sections_for_tenant(tenant_id: str | None) -> list[dict[str, Any]]:
    """Return all section records for tenant. Always filter by tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_section_for_tenant(tenant_id)
    with get_db() as session:
        rows = session.scalars(stmt).all()
        return [
            {
                "section_id": r.section_id,
                "heading_path": r.heading_path,
                "text": r.text,
                "start_char": r.start_char,
                "end_char": r.end_char,
                "version_hash": r.version_hash,
                "domain": r.domain,
                "page_type": r.page_type,
                "crawl_policy_version": r.crawl_policy_version,
            }
            for r in rows
        ]


def get_sections_by_domain(tenant_id: str | None, domain: str) -> list[dict[str, Any]]:
    """Return section records for tenant filtered by domain. Always filter by tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_section_for_tenant(tenant_id).where(Section.domain == domain)
    with get_db() as session:
        rows = session.scalars(stmt).all()
        return [
            {
                "section_id": r.section_id,
                "heading_path": r.heading_path,
                "text": r.text,
                "start_char": r.start_char,
                "end_char": r.end_char,
                "version_hash": r.version_hash,
                "domain": r.domain,
                "page_type": r.page_type,
                "crawl_policy_version": r.crawl_policy_version,
            }
            for r in rows
        ]


def get_entity_ids_for_sections(tenant_id: str | None, section_ids: Sequence[str]) -> list[str]:
    """Return entity_id list for entities whose section_id is in section_ids. Tenant-scoped."""
    tenant_id = require_tenant_id(tenant_id)
    if not section_ids:
        return []
    stmt = (
        select(Entity.entity_id)
        .select_from(Entity)
        .where(tenant_where(Entity, tenant_id), Entity.section_id.in_(section_ids))
        .distinct()
    )
    with get_db() as session:
        rows = session.scalars(stmt).all()
        return list(rows)


def get_domain_index_state(tenant_id: str | None, domain: str) -> dict[str, Any] | None:
    """Return current domain_index_state row for (tenant_id, domain), or None. Tenant-scoped."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        row = session.get(DomainIndexState, (tenant_id, domain))
        if row is None:
            return None
        return {
            "tenant_id": row.tenant_id,
            "domain": row.domain,
            "ac_version_hash": row.ac_version_hash,
            "ec_version_hash": row.ec_version_hash,
            "crawl_policy_version": row.crawl_policy_version,
            "status": row.status,
            "last_indexed_at": row.last_indexed_at,
            "last_error": row.last_error,
            "error_code": getattr(row, "error_code", None),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


def get_domain_index_states_for_tenant(tenant_id: str | None) -> dict[str, dict[str, Any]]:
    """Return all domain_index_state rows for tenant, keyed by domain. For list_domains join."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select(DomainIndexState).where(DomainIndexState.tenant_id == tenant_id)
    with get_db() as session:
        rows = session.scalars(stmt).all()
    return {
        str(r.domain): {
            "status": r.status,
            "last_indexed_at": r.last_indexed_at,
            "last_error": r.last_error,
        }
        for r in rows
    }


def upsert_domain_index_state(
    tenant_id: str | None,
    domain: str,
    **fields: Any,
) -> None:
    """Insert or update domain_index_state for (tenant_id, domain). Only provided fields are updated. Tenant-scoped."""
    tenant_id = require_tenant_id(tenant_id)
    allowed = {"ac_version_hash", "ec_version_hash", "crawl_policy_version", "status", "last_indexed_at", "last_error", "error_code"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    with get_db() as session:
        row = session.get(DomainIndexState, (tenant_id, domain))
        if row is not None:
            for key, value in updates.items():
                setattr(row, key, value)
        else:
            session.add(
                DomainIndexState(
                    tenant_id=tenant_id,
                    domain=domain,
                    status=updates.get("status", "PENDING"),
                    ac_version_hash=updates.get("ac_version_hash"),
                    ec_version_hash=updates.get("ec_version_hash"),
                    crawl_policy_version=updates.get("crawl_policy_version"),
                    last_indexed_at=updates.get("last_indexed_at"),
                    last_error=updates.get("last_error"),
                    error_code=updates.get("error_code"),
                )
            )
        session.commit()


def get_section_by_id(
    tenant_id: str | None,
    section_id: str,
) -> dict[str, Any] | None:
    """Return section by section_id for tenant, or None. Keys: text, version_hash, domain."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select_section_for_tenant(tenant_id)
        .where(Section.section_id == section_id)
        .with_only_columns(Section.text, Section.version_hash, Section.domain)
    )
    with get_db() as session:
        row = session.execute(stmt).first()
        if not row:
            return None
        return {"text": row[0], "version_hash": row[1], "domain": row[2] or ""}


def get_sections_by_query(
    tenant_id: str | None,
    query: str,
    k: int = 20,
) -> list[dict[str, Any]]:
    """Return sections matching query for tenant. Always filter by tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_section_for_tenant(tenant_id).limit(k)
    with get_db() as session:
        rows = session.scalars(stmt).all()
        return [
            {
                "section_id": r.section_id,
                "text": r.text,
                "version_hash": r.version_hash,
            }
            for r in rows
        ]


def count_raw_pages_by_domain(tenant_id: str | None, domain: str) -> int:
    """Count raw_pages for tenant filtered by domain. Strict: WHERE tenant_id=:tenant_id AND domain=:domain."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select(func.count(RawPage.id))
        .select_from(RawPage)
        .where(tenant_where(RawPage, tenant_id), RawPage.domain == domain)
    )
    with get_db() as session:
        return session.execute(stmt).scalar() or 0


def count_raw_pages_by_crawl_policy_version(
    tenant_id: str | None, crawl_policy_version: str
) -> int:
    """Count raw_pages for tenant filtered by crawl_policy_version."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select(func.count(RawPage.id))
        .select_from(RawPage)
        .where(tenant_where(RawPage, tenant_id), RawPage.crawl_policy_version == crawl_policy_version)
    )
    with get_db() as session:
        return session.execute(stmt).scalar() or 0


def count_sections_by_domain(tenant_id: str | None, domain: str) -> int:
    """Count sections for tenant filtered by domain. Strict: WHERE tenant_id=:tenant_id AND domain=:domain."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select(func.count(Section.id))
        .select_from(Section)
        .where(tenant_where(Section, tenant_id), Section.domain == domain)
    )
    with get_db() as session:
        return session.execute(stmt).scalar() or 0


def count_ac_embeddings_by_domain(tenant_id: str | None, domain: str) -> int:
    """Count ac_embeddings for tenant filtered by domain. Strict: WHERE tenant_id=:tenant_id AND domain=:domain."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select(func.count(ACEmbedding.id))
        .select_from(ACEmbedding)
        .where(tenant_where(ACEmbedding, tenant_id), ACEmbedding.domain == domain)
    )
    with get_db() as session:
        return session.execute(stmt).scalar() or 0


def count_ec_embeddings_by_domain(tenant_id: str | None, domain: str) -> int:
    """Count ec_embeddings for tenant filtered by domain. Strict: WHERE tenant_id=:tenant_id AND domain=:domain."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select(func.count(ECEmbedding.id))
        .select_from(ECEmbedding)
        .where(tenant_where(ECEmbedding, tenant_id), ECEmbedding.domain == domain)
    )
    with get_db() as session:
        return session.execute(stmt).scalar() or 0


def count_sections_by_crawl_policy_version(
    tenant_id: str | None, crawl_policy_version: str
) -> int:
    """Count sections for tenant filtered by crawl_policy_version."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select(func.count(Section.id))
        .select_from(Section)
        .where(tenant_where(Section, tenant_id), Section.crawl_policy_version == crawl_policy_version)
    )
    with get_db() as session:
        return session.execute(stmt).scalar() or 0


def get_raw_page_counts_by_domain_page_type(
    tenant_id: str | None,
) -> list[tuple[str, str, int]]:
    """Return (domain, page_type, count) for tenant's raw_pages. For demo/reporting."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select(
            func.coalesce(RawPage.domain, "(empty)"),
            func.coalesce(RawPage.page_type, "(empty)"),
            func.count(RawPage.id),
        )
        .select_from(RawPage)
        .where(tenant_where(RawPage, tenant_id))
        .group_by(RawPage.domain, RawPage.page_type)
    )
    with get_db() as session:
        rows = session.execute(stmt).all()
        return [(r[0], r[1], r[2]) for r in rows]


def get_section_stats_for_tenant(
    tenant_id: str | None,
) -> dict[str, float | int]:
    """Return {count, avg_chunk_length, min_chunk_length, max_chunk_length} for tenant's sections."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        count_stmt = select(func.count(Section.id)).select_from(Section).where(tenant_where(Section, tenant_id))
        count = session.execute(count_stmt).scalar() or 0
        if count == 0:
            return {"count": 0, "avg_chunk_length": 0.0, "min_chunk_length": 0, "max_chunk_length": 0}
        agg_stmt = (
            select(
                func.avg(func.length(Section.text)),
                func.min(func.length(Section.text)),
                func.max(func.length(Section.text)),
            )
            .select_from(Section)
            .where(tenant_where(Section, tenant_id))
        )
        agg = session.execute(agg_stmt).first()
        return {
            "count": count,
            "avg_chunk_length": float(agg[0] or 0),
            "min_chunk_length": int(agg[1] or 0),
            "max_chunk_length": int(agg[2] or 0),
        }


def get_table_counts_for_tenant(tenant_id: str | None) -> dict[str, int]:
    """Return row counts for tenant: raw_page, sections, evidence, ac_embeddings, entities, relations, ec_embeddings."""
    tenant_id = require_tenant_id(tenant_id)
    stmts = {
        "raw_page": select(func.count(RawPage.id)).select_from(RawPage).where(tenant_where(RawPage, tenant_id)),
        "sections": select(func.count(Section.id)).select_from(Section).where(tenant_where(Section, tenant_id)),
        "evidence": select(func.count(Evidence.id)).select_from(Evidence).where(tenant_where(Evidence, tenant_id)),
        "ac_embeddings": select(func.count(ACEmbedding.id)).select_from(ACEmbedding).where(tenant_where(ACEmbedding, tenant_id)),
        "entities": select(func.count(Entity.id)).select_from(Entity).where(tenant_where(Entity, tenant_id)),
        "relations": select(func.count(Relation.id)).select_from(Relation).where(tenant_where(Relation, tenant_id)),
        "ec_embeddings": select(func.count(ECEmbedding.id)).select_from(ECEmbedding).where(tenant_where(ECEmbedding, tenant_id)),
    }
    with get_db() as session:
        return {k: session.execute(s).scalar() or 0 for k, s in stmts.items()}


def get_latest_raw_page_by_canonical_url(
    tenant_id: str | None,
    canonical_url: str,
) -> dict[str, Any] | None:
    """Return latest raw_page for tenant+canonical_url, or None. Keys: id, version, content_hash.
    Ordered by version desc, id desc."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        row = (
            session.query(RawPage.id, RawPage.version, RawPage.content_hash)
            .filter(
                RawPage.tenant_id == tenant_id,
                RawPage.canonical_url == canonical_url,
            )
            .order_by(RawPage.version.desc(), RawPage.id.desc())
            .first()
        )
        if not row:
            return None
        return {"id": row[0], "version": row[1], "content_hash": row[2]}


def insert_raw_page(
    tenant_id: str | None,
    url: str,
    *,
    canonical_url: str | None = None,
    html: str | None = None,
    text: str | None = None,
    status_code: int | None = None,
    fetched_at: datetime | None = None,
    content_hash: str | None = None,
    version: int = 1,
    domain: str | None = None,
    page_type: str | None = None,
    crawl_policy_version: str | None = None,
    crawl_decision: str | None = None,
    crawl_reason: str | None = None,
) -> int:
    """Insert a raw_page and return its id."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        row = RawPage(
            tenant_id=tenant_id,
            url=url,
            canonical_url=canonical_url,
            html=html,
            text=text,
            status_code=status_code,
            fetched_at=fetched_at,
            content_hash=content_hash,
            version=version,
            domain=domain,
            page_type=page_type,
            crawl_policy_version=crawl_policy_version,
            crawl_decision=crawl_decision,
            crawl_reason=crawl_reason,
        )
        session.add(row)
        session.flush()
        return row.id


def delete_sections_for_raw_page(tenant_id: str | None, raw_page_id: int) -> int:
    """Delete all sections for a raw_page. Returns count deleted. Enforces tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = delete(Section).where(tenant_where(Section, tenant_id), Section.raw_page_id == raw_page_id)
    with get_db() as session:
        result = session.execute(stmt)
        return result.rowcount or 0


def insert_sections(
    tenant_id: str | None,
    raw_page_id: int,
    sections: Sequence[dict[str, Any]],
) -> None:
    """Bulk insert sections for a raw_page. Each dict: section_id, heading_path?, text?, start_char?, end_char?, section_hash?, version_hash?, domain?, page_type?, crawl_policy_version?."""
    tenant_id = require_tenant_id(tenant_id)
    if not sections:
        return
    with get_db() as session:
        objs = [
            Section(
                tenant_id=tenant_id,
                raw_page_id=raw_page_id,
                section_id=s["section_id"],
                heading_path=s.get("heading_path"),
                text=s.get("text"),
                start_char=s.get("start_char"),
                end_char=s.get("end_char"),
                section_hash=s.get("section_hash"),
                version_hash=s.get("version_hash"),
                domain=s.get("domain"),
                page_type=s.get("page_type"),
                crawl_policy_version=s.get("crawl_policy_version"),
            )
            for s in sections
        ]
        session.add_all(objs)


def get_evidence_ids_by_section_ids(
    tenant_id: str | None,
    section_ids: Sequence[str],
) -> dict[str, list[str]]:
    """Map section_id -> [evidence_id] for given section_ids. Always filter by tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    if not section_ids:
        return {}
    stmt = (
        select_evidence_for_tenant(tenant_id)
        .where(Evidence.section_id.in_(list(section_ids)))
        .with_only_columns(Evidence.section_id, Evidence.evidence_id)
    )
    with get_db() as session:
        rows = session.execute(stmt).all()
        out: dict[str, list[str]] = {sid: [] for sid in section_ids}
        for section_id, evidence_id in rows:
            out.setdefault(section_id, []).append(evidence_id)
        return out


def get_evidence_by_ids(
    tenant_id: str | None,
    evidence_ids: Sequence[str],
    domain: str | None = None,
) -> list[dict[str, Any]]:
    """Return evidence rows for given evidence_ids. Filter by tenant_id and optionally domain."""
    tenant_id = require_tenant_id(tenant_id)
    if not evidence_ids:
        return []
    stmt = select_evidence_for_tenant(tenant_id).where(Evidence.evidence_id.in_(list(evidence_ids)))
    if domain is not None:
        stmt = stmt.where(Evidence.domain == domain)
    with get_db() as session:
        rows = session.scalars(stmt).all()
        return [
            {
                "evidence_id": r.evidence_id,
                "tenant_id": r.tenant_id,
                "domain": r.domain,
                "section_id": r.section_id,
                "url": r.url,
                "quote_span": r.quote_span,
                "start_char": r.start_char,
                "end_char": r.end_char,
                "version_hash": r.version_hash,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def insert_evidence(
    tenant_id: str | None,
    evidence: Sequence[dict[str, Any]],
) -> None:
    """Bulk insert evidence. Each dict: evidence_id, section_id, domain, url?, quote_span?, start_char?, end_char?, version_hash?."""
    tenant_id = require_tenant_id(tenant_id)
    if not evidence:
        return
    with get_db() as session:
        objs = [
            Evidence(
                tenant_id=tenant_id,
                domain=e["domain"],
                evidence_id=e["evidence_id"],
                section_id=e["section_id"],
                url=e.get("url"),
                quote_span=e.get("quote_span"),
                start_char=e.get("start_char"),
                end_char=e.get("end_char"),
                version_hash=e.get("version_hash"),
            )
            for e in evidence
        ]
        session.add_all(objs)


def delete_entity_mentions_for_tenant(tenant_id: str | None) -> int:
    """Delete all entity_mentions for tenant. Returns count deleted. Enforces tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = delete(EntityMention).where(tenant_where(EntityMention, tenant_id))
    with get_db() as session:
        result = session.execute(stmt)
        return result.rowcount or 0


def insert_entity_mentions(
    tenant_id: str | None,
    mentions: Sequence[dict[str, Any]],
) -> None:
    """Bulk insert entity_mentions. Each dict: entity_id, section_id, start_offset, end_offset, quote_span?, confidence?."""
    tenant_id = require_tenant_id(tenant_id)
    if not mentions:
        return
    with get_db() as session:
        objs = [
            EntityMention(
                tenant_id=tenant_id,
                entity_id=m["entity_id"],
                section_id=m["section_id"],
                start_offset=m["start_offset"],
                end_offset=m["end_offset"],
                quote_span=m.get("quote_span"),
                confidence=m.get("confidence"),
            )
            for m in mentions
        ]
        session.add_all(objs)


def delete_ec_embeddings_for_tenant(tenant_id: str | None) -> int:
    """Delete all ec_embeddings for tenant. Returns count deleted. Enforces tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = delete(ECEmbedding).where(tenant_where(ECEmbedding, tenant_id))
    with get_db() as session:
        result = session.execute(stmt)
        return result.rowcount or 0


def insert_ec_embeddings(
    tenant_id: str | None,
    records: Sequence[dict[str, Any]],
) -> None:
    """Bulk insert ec_embeddings. Each dict: entity_id, embedding, domain, model?, dim?."""
    tenant_id = require_tenant_id(tenant_id)
    if not records:
        return
    with get_db() as session:
        objs = [
            ECEmbedding(
                tenant_id=tenant_id,
                domain=r["domain"],
                entity_id=r["entity_id"],
                embedding=r["embedding"],
                model=r.get("model"),
                dim=r.get("dim"),
            )
            for r in records
        ]
        session.add_all(objs)


def upsert_ec_version(tenant_id: str | None, version_hash: str) -> None:
    """Insert or update ec_version_hash for tenant."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        existing = session.get(ECVersion, tenant_id)
        if existing:
            existing.version_hash = version_hash
        else:
            session.add(ECVersion(tenant_id=tenant_id, version_hash=version_hash))


def get_ec_version(tenant_id: str | None) -> str | None:
    """Return ec_version_hash for tenant, or None."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        row = session.get(ECVersion, tenant_id)
        return row.version_hash if row else None


def get_index_versions(tenant_id: str | None) -> tuple[str, str]:
    """Return (ac_version_hash, ec_version_hash) for tenant. Uses tenant_index_versions; falls back to ec_versions for ec if missing."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        row = session.get(TenantIndexVersion, tenant_id)
        if row:
            return (row.ac_version_hash or "", row.ec_version_hash or "")
        ec = session.get(ECVersion, tenant_id)
        ec_hash = ec.version_hash if ec else ""
        return ("", ec_hash)


def upsert_tenant_index_version(
    tenant_id: str | None,
    *,
    ac_version_hash: str | None = None,
    ec_version_hash: str | None = None,
) -> None:
    """Insert or update tenant_index_versions. For tests: simulate re-ingest by changing ac_version_hash."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        row = session.get(TenantIndexVersion, tenant_id)
        if row:
            if ac_version_hash is not None:
                row.ac_version_hash = ac_version_hash
            if ec_version_hash is not None:
                row.ec_version_hash = ec_version_hash
        else:
            session.add(
                TenantIndexVersion(
                    tenant_id=tenant_id,
                    ac_version_hash=ac_version_hash or "",
                    ec_version_hash=ec_version_hash or "",
                )
            )


def upsert_entity(
    tenant_id: str | None,
    entity: dict[str, Any],
) -> None:
    """Insert or update entity by (tenant_id, entity_id). entity: entity_id, name?, canonical_name?, type?, section_id?, evidence_id?."""
    tenant_id = require_tenant_id(tenant_id)
    entity_id = entity.get("entity_id")
    if not entity_id:
        raise ValueError("entity_id is required")
    canonical = entity.get("canonical_name") or entity.get("name")
    stmt = select_entity_for_tenant(tenant_id).where(Entity.entity_id == entity_id)
    with get_db() as session:
        existing = session.scalars(stmt).first()
        if existing:
            existing.name = entity.get("name") or canonical
            existing.canonical_name = canonical
            existing.entity_type = entity.get("type")
            existing.section_id = entity.get("section_id")
            existing.evidence_id = entity.get("evidence_id")
        else:
            session.add(
                Entity(
                    tenant_id=tenant_id,
                    entity_id=entity_id,
                    name=entity.get("name") or canonical,
                    canonical_name=canonical,
                    entity_type=entity.get("type"),
                    section_id=entity.get("section_id"),
                    evidence_id=entity.get("evidence_id"),
                )
            )


def insert_relation(
    tenant_id: str | None,
    relation: dict[str, Any],
) -> None:
    """Insert a relation. relation: subject_entity_id, predicate?, object_entity_id, evidence_id?."""
    tenant_id = require_tenant_id(tenant_id)
    subj = relation.get("subject_entity_id")
    obj = relation.get("object_entity_id")
    if not subj or not obj:
        raise ValueError("subject_entity_id and object_entity_id are required")
    with get_db() as session:
        session.add(
            Relation(
                tenant_id=tenant_id,
                subject_entity_id=subj,
                predicate=relation.get("predicate"),
                object_entity_id=obj,
                evidence_id=relation.get("evidence_id"),
            )
        )


def execute_ec_retrieval(
    tenant_id: str | None,
    embedding_str: str,
    k: int,
    domain: str | None = None,
) -> list[tuple[Any, ...]]:
    """Vector search on ec_embeddings. Returns (entity_id, distance). Filter by tenant_id and optionally domain."""
    tenant_id = require_tenant_id(tenant_id)
    domain_clause = " AND ee.domain = :domain" if domain is not None else ""
    sql = text("""
        SELECT ee.entity_id, ee.embedding <-> CAST(:embedding AS vector) AS distance
        FROM ec_embeddings ee
        WHERE ee.tenant_id = :tenant_id
          """ + domain_clause + """
        ORDER BY ee.embedding <-> CAST(:embedding AS vector)
        LIMIT :k
    """)
    params: dict[str, Any] = {"tenant_id": tenant_id, "embedding": embedding_str, "k": k}
    if domain is not None:
        params["domain"] = domain
    with get_db() as session:
        return session.execute(sql, params).fetchall()


def get_entities_by_ids(
    tenant_id: str | None,
    entity_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Return entity_id -> {entity_id, canonical_name, entity_type} for given entity_ids."""
    tenant_id = require_tenant_id(tenant_id)
    if not entity_ids:
        return {}
    stmt = (
        select_entity_for_tenant(tenant_id)
        .where(Entity.entity_id.in_(list(entity_ids)))
        .with_only_columns(Entity.entity_id, Entity.canonical_name, Entity.entity_type)
    )
    with get_db() as session:
        rows = session.execute(stmt).all()
        return {
            r[0]: {"entity_id": r[0], "canonical_name": r[1] or "", "entity_type": r[2] or ""}
            for r in rows
        }


def get_entity_mentions_for_entities(
    tenant_id: str | None,
    entity_ids: Sequence[str],
    limit_per_entity: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """Return entity_id -> list of {section_id, start_offset, end_offset, quote_span}. Limit N per entity."""
    tenant_id = require_tenant_id(tenant_id)
    if not entity_ids:
        return {}

    stmt = (
        select_entity_mention_for_tenant(tenant_id)
        .where(EntityMention.entity_id.in_(list(entity_ids)))
        .with_only_columns(
            EntityMention.entity_id,
            EntityMention.section_id,
            EntityMention.start_offset,
            EntityMention.end_offset,
            EntityMention.quote_span,
            EntityMention.id,
        )
    )
    with get_db() as session:
        rows = session.execute(stmt).all()

    out: dict[str, list[dict[str, Any]]] = {eid: [] for eid in entity_ids}
    counts: dict[str, int] = {eid: 0 for eid in entity_ids}
    for r in rows:
        eid, section_id, start, end, quote, _ = r
        if counts[eid] >= limit_per_entity:
            continue
        out[eid].append({
            "section_id": section_id,
            "start_offset": start,
            "end_offset": end,
            "quote_span": quote or "",
        })
        counts[eid] += 1

    return out


def get_urls_for_section_ids(
    tenant_id: str | None,
    section_ids: Sequence[str],
) -> dict[str, str]:
    """Return section_id -> url. Joins sections with raw_page."""
    tenant_id = require_tenant_id(tenant_id)
    if not section_ids:
        return {}

    stmt = (
        select(Section.section_id, RawPage.canonical_url, RawPage.url)
        .select_from(Section)
        .join(RawPage, (Section.raw_page_id == RawPage.id) & (RawPage.tenant_id == Section.tenant_id))
        .where(tenant_where(Section, tenant_id), Section.section_id.in_(list(section_ids)))
    )
    with get_db() as session:
        rows = session.execute(stmt).fetchall()
    return {r[0]: (r[1] or r[2] or "") for r in rows}


def search_entities_text(
    tenant_id: str | None,
    query: str,
    k: int = 20,
) -> list[dict[str, Any]]:
    """Search entities by name using ILIKE. Returns [{entity_id, name, section_id, evidence_id}]."""
    tenant_id = require_tenant_id(tenant_id)
    if not query or not query.strip():
        return []
    q = query.strip()
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    stmt = (
        select_entity_for_tenant(tenant_id)
        .where(Entity.name.isnot(None), Entity.name.ilike(pattern))
        .with_only_columns(Entity.entity_id, Entity.name, Entity.section_id, Entity.evidence_id)
        .limit(k)
    )
    with get_db() as session:
        rows = session.execute(stmt).all()
        return [
            {"entity_id": r[0], "name": r[1], "section_id": r[2], "evidence_id": r[3]}
            for r in rows
        ]


def search_entities(
    tenant_id: str | None,
    query: str,
    k: int = 20,
) -> list[dict[str, Any]]:
    """Search entities by query (vector similarity on ec_embeddings). Returns list of {entity_id, name, type, distance}."""
    tenant_id = require_tenant_id(tenant_id)
    from apps.api.services.embedding_provider import embed_text

    emb = embed_text(query)
    embedding_str = "[" + ",".join(str(x) for x in emb) + "]"
    rows = execute_ec_retrieval(tenant_id, embedding_str, k)
    entity_ids = [r[0] for r in rows]
    if not entity_ids:
        return []
    entities = {}
    with get_db() as session:
        for e in (
            session.query(Entity.entity_id, Entity.name, Entity.entity_type)
            .filter(Entity.tenant_id == tenant_id, Entity.entity_id.in_(entity_ids))
            .all()
        ):
            entities[e[0]] = {"entity_id": e[0], "name": e[1], "type": e[2]}
    out = []
    for entity_id, distance in rows:
        rec = dict(entities.get(entity_id, {"entity_id": entity_id, "name": None, "type": None}))
        rec["distance"] = float(distance)
        out.append(rec)
    return out


def get_entity_by_id(
    tenant_id: str | None,
    entity_id: str,
) -> dict[str, Any] | None:
    """Return entity by entity_id for tenant, or None."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_entity_for_tenant(tenant_id).where(Entity.entity_id == entity_id)
    with get_db() as session:
        row = session.scalars(stmt).first()
        if not row:
            return None
        return {
            "entity_id": row.entity_id,
            "name": row.name,
            "type": row.entity_type,
            "section_id": row.section_id,
            "evidence_id": row.evidence_id,
        }


# ---------------------------------------------------------------------------
# Eval / Monitor
# ---------------------------------------------------------------------------


def create_eval_run(
    tenant_id: str | None,
    crawl_policy_version: str,
    ac_version_hash: str,
    ec_version_hash: str,
    git_sha: str | None = None,
) -> EvalRun:
    """Create an eval run. Returns the new EvalRun (id usable after session close)."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        session.expire_on_commit = False
        run = EvalRun(
            tenant_id=tenant_id,
            crawl_policy_version=crawl_policy_version,
            ac_version_hash=ac_version_hash,
            ec_version_hash=ec_version_hash,
            git_sha=git_sha,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


def insert_eval_results_bulk(
    tenant_id: str | None,
    run_id: UUID,
    results: list[EvalResultCreate],
) -> int:
    """Bulk insert eval results for a run. Returns count inserted."""
    tenant_id = require_tenant_id(tenant_id)
    if not results:
        return 0
    objs = [
        EvalResult(
            tenant_id=tenant_id,
            run_id=run_id,
            query_id=r.query_id,
            domain=r.domain,
            query_text=r.query_text,
            refused=r.refused,
            refusal_reason=r.refusal_reason,
            mention_ok=r.mention_ok,
            citation_ok=r.citation_ok,
            attribution_ok=r.attribution_ok,
            hallucination_flag=r.hallucination_flag,
            evidence_count=r.evidence_count,
            avg_confidence=r.avg_confidence,
            top_cited_urls=r.top_cited_urls,
            answer_preview=r.answer_preview,
        )
        for r in results
    ]
    with get_db() as session:
        session.add_all(objs)
        session.commit()
        return len(objs)


# Regex pattern for eval_domain cleanup: quote., app., secure., form. subdomains (PostgreSQL)
EVAL_DOMAIN_INVALID_PREFIX_PATTERN = "^(quote|app|secure|form)\\."


def delete_invalid_eval_domains(tenant_id: str | None) -> int:
    """Remove from eval_domain any domain matching quote./app./secure./form. prefix. Returns count deleted."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = text(
        "DELETE FROM eval_domain WHERE tenant_id = :tenant_id AND domain ~ :pattern"
    )
    with get_db() as session:
        result = session.execute(
            stmt,
            {"tenant_id": tenant_id, "pattern": EVAL_DOMAIN_INVALID_PREFIX_PATTERN},
        )
        return result.rowcount or 0


def add_eval_domain(tenant_id: str | None, domain: str) -> bool:
    """Add a domain for this tenant to be evaluated 24/7. Returns True if added, False if already exists."""
    tenant_id = require_tenant_id(tenant_id)
    domain = (domain or "").strip()
    if not domain:
        return False
    with get_db() as session:
        existing = session.scalars(
            select(EvalDomain).where(tenant_where(EvalDomain, tenant_id), EvalDomain.domain == domain)
        ).first()
        if existing:
            return False
        session.add(EvalDomain(tenant_id=tenant_id, domain=domain))
        session.commit()
        return True


def list_eval_domains(tenant_id: str | None) -> list[str]:
    """Return list of domains added for this tenant (for 24/7 eval)."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select(EvalDomain.domain).where(tenant_where(EvalDomain, tenant_id)).order_by(EvalDomain.domain)
    with get_db() as session:
        return list(session.scalars(stmt).all())


def delete_domain_data(tenant_id: str | None, domain: str) -> None:
    """Delete all rows for this tenant+domain in dependency order. Uses one transaction; rollback on any failure.

    Note: domain_*_job tables store domains as a JSONB array of strings (e.g. ["example.com"]).
    Use domains ? :domain to match rows whose array contains the domain string.
    """
    tenant_id = require_tenant_id(tenant_id)
    domain = (domain or "").strip().lower()
    if not domain:
        raise ValueError("domain is required")
    params = {"tid": tenant_id, "domain": domain}
    with get_db() as session:
        # Relations reference evidence; delete first
        logger.info("delete_domain_data removing relations (via evidence) tenant=%s domain=%s", tenant_id, domain)
        session.execute(
            text(
                "DELETE FROM relations WHERE tenant_id = :tid AND evidence_id IN "
                "(SELECT evidence_id FROM evidence WHERE tenant_id = :tid AND domain = :domain)"
            ),
            params,
        )
        logger.info("delete_domain_data removing evidence, ac_embeddings, ec_embeddings tenant=%s domain=%s", tenant_id, domain)
        session.execute(text("DELETE FROM evidence WHERE tenant_id = :tid AND domain = :domain"), params)
        session.execute(text("DELETE FROM ac_embeddings WHERE tenant_id = :tid AND domain = :domain"), params)
        session.execute(text("DELETE FROM ec_embeddings WHERE tenant_id = :tid AND domain = :domain"), params)
        logger.info("delete_domain_data removing entity_mentions, entities, sections tenant=%s domain=%s", tenant_id, domain)
        session.execute(
            text(
                "DELETE FROM entity_mentions WHERE tenant_id = :tid AND section_id IN "
                "(SELECT section_id FROM sections WHERE tenant_id = :tid AND domain = :domain)"
            ),
            params,
        )
        session.execute(
            text(
                "DELETE FROM entities WHERE tenant_id = :tid AND section_id IN "
                "(SELECT section_id FROM sections WHERE tenant_id = :tid AND domain = :domain)"
            ),
            params,
        )
        session.execute(text("DELETE FROM sections WHERE tenant_id = :tid AND domain = :domain"), params)
        logger.info("delete_domain_data removing raw_page, eval_result tenant=%s domain=%s", tenant_id, domain)
        session.execute(text("DELETE FROM raw_page WHERE tenant_id = :tid AND domain = :domain"), params)
        session.execute(text("DELETE FROM eval_result WHERE tenant_id = :tid AND domain = :domain"), params)
        logger.info("delete_domain_data removing domain_ingest_job tenant=%s domain=%s", tenant_id, domain)
        session.execute(
            text("DELETE FROM domain_ingest_job WHERE tenant_id = :tid AND domain = :domain"),
            params,
        )
        # domains column is JSONB array of strings; ? checks whether the domain string exists in the array
        logger.info("delete_domain_data removing domain_eval_job tenant=%s domain=%s", tenant_id, domain)
        session.execute(
            text(
                "DELETE FROM domain_eval_job WHERE tenant_id = :tid AND domains ? :domain"
            ),
            params,
        )
        logger.info("delete_domain_data removing domain_orchestrate_job tenant=%s domain=%s", tenant_id, domain)
        session.execute(
            text(
                "DELETE FROM domain_orchestrate_job WHERE tenant_id = :tid AND domains ? :domain"
            ),
            params,
        )
        logger.info("delete_domain_data removing domain_eval_orchestration_job tenant=%s domain=%s", tenant_id, domain)
        session.execute(
            text(
                "DELETE FROM domain_eval_orchestration_job WHERE tenant_id = :tid AND domains ? :domain"
            ),
            params,
        )
        logger.info("delete_domain_data removing domain_index_state, eval_domain tenant=%s domain=%s", tenant_id, domain)
        session.execute(
            text("DELETE FROM domain_index_state WHERE tenant_id = :tid AND domain = :domain"),
            params,
        )
        session.execute(text("DELETE FROM eval_domain WHERE tenant_id = :tid AND domain = :domain"), params)


def get_latest_eval_run(tenant_id: str | None) -> EvalRun | None:
    """Return latest eval_run for tenant by created_at desc, or None."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select_eval_run_for_tenant(tenant_id)
        .order_by(EvalRun.created_at.desc())
        .limit(1)
    )
    with get_db() as session:
        return session.scalars(stmt).first()


def get_eval_run_by_id(tenant_id: str | None, run_id: UUID) -> EvalRun | None:
    """Return eval_run by id for tenant, or None."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_eval_run_for_tenant(tenant_id).where(EvalRun.id == run_id)
    with get_db() as session:
        return session.scalars(stmt).first()


def aggregate_kpis_for_run(tenant_id: str | None, run_id: UUID) -> dict[str, Any]:
    """Aggregate KPIs for run: rates via AVG(CASE WHEN flag THEN 1 ELSE 0 END), hallucinations as count.
    Returns mention_rate, citation_rate, attribution_accuracy, hallucinations (count), composite_index."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select(
            func.avg(case((EvalResult.mention_ok == True, 1), else_=0)).label("mention_rate"),
            func.avg(case((EvalResult.citation_ok == True, 1), else_=0)).label("citation_rate"),
            func.avg(case((EvalResult.refused == True, 1), else_=0)).label("refusal_rate"),
            func.avg(case((EvalResult.attribution_ok == True, 1), else_=0)).label("attribution_accuracy"),
            func.sum(case((EvalResult.hallucination_flag == True, 1), else_=0)).label("hallucinations"),
            func.count(EvalResult.id).label("total"),
        )
        .select_from(EvalResult)
        .where(tenant_where(EvalResult, tenant_id), EvalResult.run_id == run_id)
    )
    with get_db() as session:
        row = session.execute(stmt).one_or_none()
    if not row or (row.total or 0) == 0:
        return {
            "mention_rate": 0.0,
            "citation_rate": 0.0,
            "attribution_accuracy": 0.0,
            "hallucinations": 0,
            "composite_index": 0.0,
        }
    mr = float(row.mention_rate or 0.0)
    cr = float(row.citation_rate or 0.0)
    rr = float(row.refusal_rate or 0.0)
    aa = float(row.attribution_accuracy or 0.0)
    hall = int(row.hallucinations or 0)
    total = int(row.total or 1)
    hall_rate = hall / total
    composite_index = max(0.0, min(1.0, (mr + cr + aa) / 3.0 - hall_rate * 0.1))
    return {
        "mention_rate": mr,
        "citation_rate": cr,
        "refusal_rate": rr,
        "attribution_accuracy": aa,
        "hallucinations": hall,
        "composite_index": round(composite_index, 4),
    }


def get_trends(
    tenant_id: str | None,
    days: int = 30,
    mode: str = "per_run",
) -> list[dict[str, Any]]:
    """Return trend points: one per run in last N days (mode=per_run). Each point has ts, rates, hallucinations, composite_index, run_id."""
    tenant_id = require_tenant_id(tenant_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select_eval_run_for_tenant(tenant_id)
        .where(EvalRun.created_at >= cutoff)
        .order_by(EvalRun.created_at.desc())
    )
    with get_db() as session:
        runs = list(session.scalars(stmt).all())
    points: list[dict[str, Any]] = []
    for run in runs:
        kpis = aggregate_kpis_for_run(tenant_id, run.id)
        ts = run.created_at.isoformat() if run.created_at else ""
        points.append({
            "ts": ts,
            "mention_rate": kpis["mention_rate"],
            "citation_rate": kpis["citation_rate"],
            "attribution_accuracy": kpis["attribution_accuracy"],
            "hallucinations": float(kpis["hallucinations"]),
            "composite_index": kpis["composite_index"],
            "run_id": run.id,
        })
    return points


def list_eval_results(
    tenant_id: str | None,
    run_id: UUID,
    domain: str | None = None,
    failed_only: bool = False,
    refused_only: bool = False,
    limit: int = 500,
    offset: int = 0,
) -> list[EvalResult]:
    """List eval results for run. Joins eval_run for tenant. Filters: domain, failed_only, refused_only.
    failed_only: refused OR hallucination_flag OR NOT mention_ok OR NOT citation_ok OR NOT attribution_ok.
    refused_only: only refused rows. Order: hallucination_flag desc, refused desc, citation_ok asc, evidence_count asc."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select_eval_result_for_tenant(tenant_id)
        .join(EvalRun, (EvalResult.run_id == EvalRun.id) & tenant_where(EvalRun, tenant_id))
        .where(EvalResult.run_id == run_id)
    )
    if domain is not None:
        stmt = stmt.where(EvalResult.domain == domain)
    if refused_only:
        stmt = stmt.where(EvalResult.refused == True)
    elif failed_only:
        stmt = stmt.where(
            or_(
                EvalResult.refused == True,
                EvalResult.hallucination_flag == True,
                EvalResult.mention_ok == False,
                EvalResult.citation_ok == False,
                EvalResult.attribution_ok == False,
            )
        )
    stmt = stmt.order_by(
        EvalResult.hallucination_flag.desc(),
        EvalResult.refused.desc(),
        EvalResult.citation_ok.asc(),
        EvalResult.evidence_count.asc(),
    ).limit(limit).offset(offset)
    with get_db() as session:
        return list(session.scalars(stmt).all())


def get_eval_metrics_for_run(
    tenant_id: str | None,
    run_id: UUID,
) -> dict[str, Any]:
    """Aggregate mention_rate, citation_rate, attribution_rate, hallucination_rate for run.
    Returns {overall: {...}, per_domain: {domain: {...}}}."""
    tenant_id = require_tenant_id(tenant_id)
    # PostgreSQL: cast boolean to Integer (0/1) before avg; cannot cast boolean to Float directly
    overall_stmt = (
        select(
            func.avg(cast(EvalResult.mention_ok, Integer)).label("mention_rate"),
            func.avg(cast(EvalResult.citation_ok, Integer)).label("citation_rate"),
            func.avg(cast(EvalResult.attribution_ok, Integer)).label("attribution_rate"),
            func.avg(cast(EvalResult.hallucination_flag, Integer)).label("hallucination_rate"),
        )
        .select_from(EvalResult)
        .where(tenant_where(EvalResult, tenant_id), EvalResult.run_id == run_id)
    )
    domain_stmt = (
        select(
            EvalResult.domain,
            func.avg(cast(EvalResult.mention_ok, Integer)).label("mention_rate"),
            func.avg(cast(EvalResult.citation_ok, Integer)).label("citation_rate"),
            func.avg(cast(EvalResult.attribution_ok, Integer)).label("attribution_rate"),
            func.avg(cast(EvalResult.hallucination_flag, Integer)).label("hallucination_rate"),
        )
        .where(tenant_where(EvalResult, tenant_id), EvalResult.run_id == run_id)
        .group_by(EvalResult.domain)
    )
    with get_db() as session:
        overall_row = session.execute(overall_stmt).one_or_none()
        domain_rows = session.execute(domain_stmt).all()

    def _rates(r) -> dict[str, float]:
        return {
            "mention_rate": float(r.mention_rate or 0.0),
            "citation_rate": float(r.citation_rate or 0.0),
            "attribution_rate": float(r.attribution_rate or 0.0),
            "hallucination_rate": float(r.hallucination_rate or 0.0),
        }

    overall = _rates(overall_row) if overall_row else {
        "mention_rate": 0.0,
        "citation_rate": 0.0,
        "attribution_rate": 0.0,
        "hallucination_rate": 0.0,
    }
    per_domain = {row.domain: _rates(row) for row in domain_rows}
    return {"overall": overall, "per_domain": per_domain}


def get_latest_domain_eval_snapshots(tenant_id: str | None) -> dict[str, dict[str, Any]]:
    """Return per-domain eval aggregates (all-time per tenant+domain) plus latest run metadata.
    Status should be interpreted by callers from total/refused/ok counts."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = text(
        """
        WITH latest_run_per_domain AS (
            SELECT DISTINCT ON (er.domain)
                   er.domain,
                   er.run_id AS last_run_id,
                   r.created_at AS last_run_created_at
            FROM eval_result er
            JOIN eval_run r ON r.id = er.run_id AND r.tenant_id = er.tenant_id
            WHERE er.tenant_id = :tenant_id
            ORDER BY er.domain, r.created_at DESC, er.id DESC
        ),
        all_time_agg AS (
            SELECT er.domain,
                   AVG(CAST(er.mention_ok AS INTEGER))::float AS mention_rate,
                   AVG(CAST(er.citation_ok AS INTEGER))::float AS citation_rate,
                   AVG(CAST(er.attribution_ok AS INTEGER))::float AS attribution_rate,
                   AVG(CAST(er.hallucination_flag AS INTEGER))::float AS hallucination_rate,
                   COUNT(*)::int AS total_rows,
                   SUM(CASE WHEN er.refused THEN 1 ELSE 0 END)::int AS refused_rows,
                   STRING_AGG(DISTINCT NULLIF(TRIM(er.refusal_reason), ''), '; ') AS refusal_reason_summary
            FROM eval_result er
            WHERE er.tenant_id = :tenant_id
            GROUP BY er.domain
        )
        SELECT a.domain,
               l.last_run_id AS run_id,
               l.last_run_created_at AS run_created_at,
               COALESCE(a.mention_rate, 0.0) AS mention_rate,
               COALESCE(a.citation_rate, 0.0) AS citation_rate,
               COALESCE(a.attribution_rate, 0.0) AS attribution_rate,
               COALESCE(a.hallucination_rate, 0.0) AS hallucination_rate,
               COALESCE(a.total_rows, 0) AS total_rows,
               COALESCE(a.refused_rows, 0) AS refused_rows,
               COALESCE(a.total_rows - a.refused_rows, 0) AS ok_rows,
               COALESCE(a.refusal_reason_summary, '') AS refusal_reason_summary
        FROM all_time_agg a
        LEFT JOIN latest_run_per_domain l
          ON l.domain = a.domain
        """
    )
    with get_db() as session:
        rows = session.execute(stmt, {"tenant_id": tenant_id}).mappings().all()

    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        out[str(r["domain"])] = {
            "run_id": (str(r["run_id"]) if r.get("run_id") else None),
            "run_created_at": r["run_created_at"],
            "mention_rate": float(r["mention_rate"] or 0.0),
            "citation_rate": float(r["citation_rate"] or 0.0),
            "attribution_rate": float(r["attribution_rate"] or 0.0),
            "hallucination_rate": float(r["hallucination_rate"] or 0.0),
            "total_results": int(r["total_rows"] or 0),
            "refused_count": int(r["refused_rows"] or 0),
            "ok_count": int(r["ok_rows"] or 0),
            "refusal_reason_summary": str(r["refusal_reason_summary"] or "") or None,
        }
    return out


def get_domain_aggregates_from_eval_result(tenant_id: str | None) -> list[dict[str, Any]]:
    """Return per-domain aggregates from eval_domain LEFT JOIN eval_result for tenant.
    Includes all domains from eval_domain plus any domain that has eval_result rows.
    Rates are 0..1 floats; total_results is count of eval_result rows."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = text(
        """
        WITH domains AS (
            SELECT domain, tenant_id FROM eval_domain WHERE tenant_id = :tenant_id
            UNION
            SELECT DISTINCT domain, tenant_id FROM eval_result WHERE tenant_id = :tenant_id
        )
        SELECT
            d.domain,
            COUNT(r.id)::int AS total_results,
            COALESCE(SUM(CASE WHEN r.refused THEN 1 ELSE 0 END), 0)::int AS refused_count,
            COALESCE(COUNT(r.id) - SUM(CASE WHEN r.refused THEN 1 ELSE 0 END), 0)::int AS ok_count,
            COALESCE(AVG(CASE WHEN r.mention_ok THEN 1 ELSE 0 END)::float, 0.0) AS mention_rate,
            COALESCE(AVG(CASE WHEN r.citation_ok THEN 1 ELSE 0 END)::float, 0.0) AS citation_rate,
            COALESCE(AVG(CASE WHEN r.attribution_ok THEN 1 ELSE 0 END)::float, 0.0) AS attribution_rate,
            COALESCE(AVG(CASE WHEN r.hallucination_flag THEN 1 ELSE 0 END)::float, 0.0) AS hallucination_rate,
            STRING_AGG(DISTINCT NULLIF(TRIM(r.refusal_reason), ''), '; ') AS refusal_reason_summary,
            (SELECT r2.run_id FROM eval_result r2
             WHERE r2.tenant_id = d.tenant_id AND r2.domain = d.domain
             ORDER BY r2.id DESC LIMIT 1) AS last_run_id,
            (SELECT r3.created_at FROM eval_run r3
             WHERE r3.tenant_id = d.tenant_id AND r3.id = (
                 SELECT r2.run_id FROM eval_result r2
                 WHERE r2.tenant_id = d.tenant_id AND r2.domain = d.domain
                 ORDER BY r2.id DESC LIMIT 1
             ) LIMIT 1) AS last_created_at
        FROM domains d
        LEFT JOIN eval_result r ON r.domain = d.domain AND r.tenant_id = d.tenant_id
        WHERE d.tenant_id = :tenant_id
        GROUP BY d.domain, d.tenant_id
        ORDER BY d.domain
        """
    )
    with get_db() as session:
        rows = session.execute(stmt, {"tenant_id": tenant_id}).mappings().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "domain": str(r["domain"]),
            "total_results": int(r["total_results"] or 0),
            "refused_count": int(r["refused_count"] or 0),
            "ok_count": int(r["ok_count"] or 0),
            "mention_rate": float(r["mention_rate"] or 0.0),
            "citation_rate": float(r["citation_rate"] or 0.0),
            "attribution_rate": float(r["attribution_rate"] or 0.0),
            "hallucination_rate": float(r["hallucination_rate"] or 0.0),
            "refusal_reason_summary": str(r["refusal_reason_summary"] or "") or None,
            "last_run_id": str(r["last_run_id"]) if r.get("last_run_id") else None,
            "last_created_at": r.get("last_created_at"),
        })
    return out


def list_eval_runs(
    tenant_id: str | None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[EvalRun]:
    """List eval runs for tenant, ordered by created_at desc."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_eval_run_for_tenant(tenant_id)
    if date_from is not None:
        stmt = stmt.where(func.date(EvalRun.created_at) >= date_from)
    if date_to is not None:
        stmt = stmt.where(func.date(EvalRun.created_at) <= date_to)
    stmt = stmt.order_by(EvalRun.created_at.desc()).limit(limit).offset(offset)
    with get_db() as session:
        return list(session.scalars(stmt).all())


def get_eval_results(
    tenant_id: str | None,
    run_id: UUID,
    domain: str | None = None,
    query_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[EvalResult]:
    """Get eval results for a run. Joins eval_run for date filters. Ordered by created_at desc."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select_eval_result_for_tenant(tenant_id)
        .join(EvalRun, (EvalResult.run_id == EvalRun.id) & tenant_where(EvalRun, tenant_id))
        .where(EvalResult.run_id == run_id)
    )
    if domain is not None:
        stmt = stmt.where(EvalResult.domain == domain)
    if query_id is not None:
        stmt = stmt.where(EvalResult.query_id == query_id)
    if date_from is not None:
        stmt = stmt.where(func.date(EvalRun.created_at) >= date_from)
    if date_to is not None:
        stmt = stmt.where(func.date(EvalRun.created_at) <= date_to)
    # EvalResult has no created_at; order by id desc for stable ordering
    stmt = stmt.order_by(EvalResult.id.desc()).limit(limit).offset(offset)
    with get_db() as session:
        return list(session.scalars(stmt).all())


def create_monitor_event(
    tenant_id: str | None,
    event_type: str,
    severity: str,
    details_json: dict | list | None = None,
) -> MonitorEvent:
    """Create a monitor event. Returns the new MonitorEvent."""
    tenant_id = require_tenant_id(tenant_id)
    with get_db() as session:
        evt = MonitorEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            severity=severity,
            details_json=details_json,
        )
        session.add(evt)
        session.commit()
        session.refresh(evt)
        return evt


def list_monitor_events(
    tenant_id: str | None,
    date_from: date | None = None,
    date_to: date | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[MonitorEvent]:
    """List monitor events for tenant, ordered by created_at desc."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_monitor_event_for_tenant(tenant_id)
    if date_from is not None:
        stmt = stmt.where(func.date(MonitorEvent.created_at) >= date_from)
    if date_to is not None:
        stmt = stmt.where(func.date(MonitorEvent.created_at) <= date_to)
    if event_type is not None:
        stmt = stmt.where(MonitorEvent.event_type == event_type)
    if severity is not None:
        stmt = stmt.where(MonitorEvent.severity == severity)
    stmt = stmt.order_by(MonitorEvent.created_at.desc()).limit(limit).offset(offset)
    with get_db() as session:
        return list(session.scalars(stmt).all())
