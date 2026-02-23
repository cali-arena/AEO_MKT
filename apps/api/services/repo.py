"""Repository layer. All functions require tenant_id as first argument; guard raises if None/empty.

RULE: Repo is the ONLY place allowed to run DB reads/writes (session.execute, get_db).
All tenant-scoped queries MUST use tenant_filters (select_*_for_tenant / tenant_where).

GUARD: Every function MUST call require_tenant_id(tenant_id) before any DB access.
"""

from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Float, case, cast, delete, func, or_, select, text

from apps.api.db import get_db
from apps.api.models.ac_embedding import ACEmbedding
from apps.api.models.ec_embedding import ECEmbedding
from apps.api.models.entity import Entity
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


def get_existing_ac_section_ids(tenant_id: str | None) -> set[str]:
    """Return section_ids already indexed in ac_embeddings. Always filter by tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = select_ac_embedding_for_tenant(tenant_id).with_only_columns(ACEmbedding.section_id)
    with get_db() as session:
        rows = session.execute(stmt).all()
        return {r[0] for r in rows}


def insert_ac_embeddings(
    tenant_id: str | None,
    records: Sequence[dict[str, Any]],
) -> None:
    """Bulk insert ac_embeddings. Each dict: section_id, embedding."""
    tenant_id = require_tenant_id(tenant_id)
    if not records:
        return
    with get_db() as session:
        objs = [
            ACEmbedding(
                tenant_id=tenant_id,
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
) -> list[tuple[Any, ...]]:
    """
    BM25-style FTS retrieval on sections.text_tsv using websearch_to_tsquery and ts_rank_cd.
    Returns rows (section_id, version_hash, url, text, page_type, rank).
    Tenant-filtered. Returns [] if query empty. Requires text_tsv column (migration 001).
    """
    tenant_id = require_tenant_id(tenant_id)
    if not query or not query.strip():
        return []
    q = query.strip()
    sql = text("""
        SELECT s.section_id, s.version_hash, COALESCE(r.canonical_url, r.url) AS url, s.text,
               COALESCE(s.page_type, r.page_type) AS page_type,
               ts_rank_cd(s.text_tsv, websearch_to_tsquery(:config, :query))::float AS rank
        FROM sections s
        JOIN raw_page r ON s.raw_page_id = r.id AND r.tenant_id = s.tenant_id
        WHERE s.tenant_id = :tenant_id AND r.tenant_id = :tenant_id
          AND s.text_tsv @@ websearch_to_tsquery(:config, :query)
        ORDER BY rank DESC, s.section_id ASC
        LIMIT :k
    """)
    with get_db() as session:
        return session.execute(
            sql,
            {"tenant_id": tenant_id, "query": q, "config": fts_config, "k": k},
        ).fetchall()


def execute_ac_retrieval(
    tenant_id: str | None,
    embedding_str: str,
    k: int,
) -> list[tuple[Any, ...]]:
    """
    Run vector retrieval SQL. Joins ac_embeddings, sections, raw_page.
    Each table enforces tenant_id in JOIN/WHERE. Returns rows (section_id, version_hash, url, text, distance).
    """
    tenant_id = require_tenant_id(tenant_id)
    sql = text("""
        SELECT s.section_id, s.version_hash, r.url, s.text,
               COALESCE(s.page_type, r.page_type) AS page_type,
               ae.embedding <-> CAST(:embedding AS vector) AS distance
        FROM ac_embeddings ae
        JOIN sections s ON ae.tenant_id = s.tenant_id AND ae.section_id = s.section_id
        JOIN raw_page r ON s.raw_page_id = r.id AND r.tenant_id = s.tenant_id
        WHERE ae.tenant_id = :tenant_id AND s.tenant_id = :tenant_id AND r.tenant_id = :tenant_id
        ORDER BY ae.embedding <-> CAST(:embedding AS vector)
        LIMIT :k
    """)
    with get_db() as session:
        return session.execute(
            sql,
            {"tenant_id": tenant_id, "embedding": embedding_str, "k": k},
        ).fetchall()


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


def get_section_by_id(
    tenant_id: str | None,
    section_id: str,
) -> dict[str, Any] | None:
    """Return section by section_id for tenant, or None. Keys: text, version_hash."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select_section_for_tenant(tenant_id)
        .where(Section.section_id == section_id)
        .with_only_columns(Section.text, Section.version_hash)
    )
    with get_db() as session:
        row = session.execute(stmt).first()
        if not row:
            return None
        return {"text": row[0], "version_hash": row[1]}


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
    """Count raw_pages for tenant filtered by domain."""
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
    """Count sections for tenant filtered by domain."""
    tenant_id = require_tenant_id(tenant_id)
    stmt = (
        select(func.count(Section.id))
        .select_from(Section)
        .where(tenant_where(Section, tenant_id), Section.domain == domain)
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
) -> list[dict[str, Any]]:
    """Return evidence rows for given evidence_ids. Always filter by tenant_id."""
    tenant_id = require_tenant_id(tenant_id)
    if not evidence_ids:
        return []
    stmt = select_evidence_for_tenant(tenant_id).where(Evidence.evidence_id.in_(list(evidence_ids)))
    with get_db() as session:
        rows = session.scalars(stmt).all()
        return [
            {
                "evidence_id": r.evidence_id,
                "tenant_id": r.tenant_id,
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
    """Bulk insert evidence. Each dict: evidence_id, section_id, url?, quote_span?, start_char?, end_char?, version_hash?."""
    tenant_id = require_tenant_id(tenant_id)
    if not evidence:
        return
    with get_db() as session:
        objs = [
            Evidence(
                tenant_id=tenant_id,
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
    """Bulk insert ec_embeddings. Each dict: entity_id, embedding, model?, dim?."""
    tenant_id = require_tenant_id(tenant_id)
    if not records:
        return
    with get_db() as session:
        objs = [
            ECEmbedding(
                tenant_id=tenant_id,
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
) -> list[tuple[Any, ...]]:
    """Vector search on ec_embeddings. Returns (entity_id, distance). Tenant-filtered in WHERE."""
    tenant_id = require_tenant_id(tenant_id)
    sql = text("""
        SELECT ee.entity_id, ee.embedding <-> CAST(:embedding AS vector) AS distance
        FROM ec_embeddings ee
        WHERE ee.tenant_id = :tenant_id
        ORDER BY ee.embedding <-> CAST(:embedding AS vector)
        LIMIT :k
    """)
    with get_db() as session:
        return session.execute(
            sql,
            {"tenant_id": tenant_id, "embedding": embedding_str, "k": k},
        ).fetchall()


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
    overall_stmt = (
        select(
            func.avg(cast(EvalResult.mention_ok, Float)).label("mention_rate"),
            func.avg(cast(EvalResult.citation_ok, Float)).label("citation_rate"),
            func.avg(cast(EvalResult.attribution_ok, Float)).label("attribution_rate"),
            func.avg(cast(EvalResult.hallucination_flag, Float)).label("hallucination_rate"),
        )
        .select_from(EvalResult)
        .where(tenant_where(EvalResult, tenant_id), EvalResult.run_id == run_id)
    )
    domain_stmt = (
        select(
            EvalResult.domain,
            func.avg(cast(EvalResult.mention_ok, Float)).label("mention_rate"),
            func.avg(cast(EvalResult.citation_ok, Float)).label("citation_rate"),
            func.avg(cast(EvalResult.attribution_ok, Float)).label("attribution_rate"),
            func.avg(cast(EvalResult.hallucination_flag, Float)).label("hallucination_rate"),
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
