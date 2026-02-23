"""Tenant/version-safe answer cache. Uses Postgres answer_cache table."""

import hashlib
import logging
import os
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models.answer_cache import AnswerCache
from apps.api.repositories.tenant_filters import tenant_where
from apps.api.services.tenant_guard import require_tenant_id


def normalize_query(q: str) -> str:
    """Trim, collapse whitespace, lowercase."""
    if not q:
        return ""
    return " ".join(re.split(r"\s+", q.strip().lower()))


def compute_query_hash(normalized_query: str) -> str:
    """SHA256 of normalized query, first 16 hex chars."""
    return hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()[:16]


def make_cache_key(
    tenant_id: str,
    query_hash: str,
    ac_version_hash: str,
    ec_version_hash: str,
    crawl_policy_version: str,
) -> str:
    """Build cache key. Exactly: tenant_id:query_hash:ac_version_hash:ec_version_hash:crawl_policy_version."""
    tenant_id = require_tenant_id(tenant_id)
    return f"{tenant_id}:{query_hash}:{ac_version_hash}:{ec_version_hash}:{crawl_policy_version}"


def build_cache_key(
    tenant_id: str | None,
    query_hash: str,
    ac_version_hash: str,
    ec_version_hash: str,
) -> str:
    """
    Legacy cache key helper (without crawl_policy_version). Test compatibility only.

    Deprecated: use make_cache_key(tenant_id, query_hash, ac_version_hash, ec_version_hash, crawl_policy_version).
    Raises RuntimeError if ENV != "test".
    """
    if os.getenv("ENV") != "test":
        raise RuntimeError(
            "build_cache_key is deprecated and test-only. Use make_cache_key(tenant_id, query_hash, "
            "ac_version_hash, ec_version_hash, crawl_policy_version) instead."
        )
    logging.getLogger(__name__).warning(
        "build_cache_key is deprecated; use make_cache_key with crawl_policy_version"
    )
    tenant_id = require_tenant_id(tenant_id)
    return f"{tenant_id}:{query_hash}:{ac_version_hash}:{ec_version_hash}"


def cache_get(db: Session, key: str, tenant_id: str) -> dict[str, Any] | None:
    """
    Fetch cache entry by key. Enforces tenant match (defense in depth).
    Returns parsed payload or None if not found, expired, or tenant mismatch.
    """
    stmt = (
        select(AnswerCache)
        .where(AnswerCache.cache_key == key)
        .where(tenant_where(AnswerCache, tenant_id))
    )
    row = db.scalars(stmt).first()
    if not row:
        return None
    if row.expires_at and row.expires_at < datetime.now(timezone.utc):
        return None
    return json.loads(row.payload_json)


def cache_set(
    db: Session,
    key: str,
    tenant_id: str,
    query_hash: str,
    payload: dict[str, Any],
    ttl_seconds: int | None = None,
) -> None:
    """Insert or replace cache entry."""
    payload_json = json.dumps(payload, ensure_ascii=False)
    expires_at = None
    if ttl_seconds is not None and ttl_seconds > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    stmt = (
        select(AnswerCache)
        .where(AnswerCache.cache_key == key)
        .where(tenant_where(AnswerCache, tenant_id))
    )
    row = db.scalars(stmt).first()
    if row:
        row.payload_json = payload_json
        row.expires_at = expires_at
    else:
        db.add(
            AnswerCache(
                cache_key=key,
                tenant_id=tenant_id,
                query_hash=query_hash,
                payload_json=payload_json,
                expires_at=expires_at,
            )
        )
