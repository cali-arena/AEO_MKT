"""Ingest helpers for single pages and domain-level sync ingestion."""

import logging
from datetime import datetime
from typing import Any

from apps.api.services.extract import extract_main_text
from apps.api.services.index_ec import index_ec
from apps.api.services.metadata import extract_domain
from apps.api.services.normalize import content_hash
from apps.api.services.repo import get_latest_raw_page_by_canonical_url, insert_raw_page

logger = logging.getLogger(__name__)


def ingest_page(
    tenant_id: str,
    url: str,
    fetch_result: dict[str, Any],
    *,
    domain: str | None = None,
    page_type: str | None = None,
    crawl_policy_version: str | None = None,
    crawl_decision: str | None = None,
    crawl_reason: str | None = None,
    extracted_text: str | None = None,
    precomputed_content_hash: str | None = None,
) -> dict[str, Any]:
    """
    Store or reuse raw_page. When extracted_text and content_hash are provided (from pipeline),
    use them; otherwise extract from html and compute hash.
    fetch_result: {final_url, status_code, html, fetched_at}.
    raw_page stores normalized text and content_hash.
    Returns {raw_page_id, unchanged}. unchanged=True when content_hash matched; skip re-sectionize.
    """
    html = fetch_result.get("html", "")
    status_code = fetch_result.get("status_code")
    fetched_at: datetime | None = fetch_result.get("fetched_at")
    final_url = fetch_result.get("final_url") or url
    if domain is None:
        domain = extract_domain(final_url)

    if extracted_text is not None and precomputed_content_hash is not None:
        text = extracted_text
        new_hash = precomputed_content_hash
    else:
        text = extract_main_text(html)
        new_hash = content_hash(text)
    logger.info("Ingesting url=%s text_len=%d content_hash=%s", url, len(text), new_hash[:16])

    latest = get_latest_raw_page_by_canonical_url(tenant_id, final_url)
    if latest is None:
        version = 1
    elif latest["content_hash"] == new_hash:
        logger.info("raw_page unchanged url=%s raw_page_id=%s", url, latest["id"])
        return {"raw_page_id": latest["id"], "unchanged": True, "changed": False}
    else:
        version = latest["version"] + 1
    raw_page_id = insert_raw_page(
        tenant_id,
        url,
        canonical_url=final_url,
        html=html,
        text=text,
        status_code=status_code,
        fetched_at=fetched_at,
        content_hash=new_hash,
        version=version,
        domain=domain,
        page_type=page_type,
        crawl_policy_version=crawl_policy_version,
        crawl_decision=crawl_decision,
        crawl_reason=crawl_reason,
    )
    logger.info("Stored raw_page id=%s url=%s version=%s", raw_page_id, url, version)
    return {"raw_page_id": raw_page_id, "unchanged": False, "changed": True}


def _normalize_domain(domain: str) -> str:
    value = (domain or "").strip().lower()
    value = value.replace("\\", "/")
    if "://" in value:
        value = value.split("://", 1)[1]
    value = value.split("/", 1)[0]
    value = value.split("?", 1)[0]
    value = value.split("#", 1)[0]
    return value.strip(".")


def _candidate_urls_for_domain(domain: str) -> list[str]:
    normalized = _normalize_domain(domain)
    if not normalized:
        return []
    return [f"https://{normalized}", f"http://{normalized}"]


def ingest_domain_sync(tenant_id: str, domain: str) -> dict[str, Any]:
    """
    Crawl+ingest+sectionize+index a domain before eval.
    Uses Day1 pipeline for AC and then EC indexing for evidence/entity embeddings.
    """
    normalized_domain = _normalize_domain(domain)
    if not normalized_domain:
        raise ValueError("domain is required")

    urls = _candidate_urls_for_domain(normalized_domain)
    logger.info("ingest_start tenant_id=%s domain=%s", tenant_id, normalized_domain)

    last_error: Exception | None = None
    for url in urls:
        try:
            # Import here to avoid module import cycle (pipeline imports ingest_page).
            from apps.api.services.pipeline import run_day1_pipeline

            result = run_day1_pipeline(tenant_id, url)
            raw_page_id = result.get("raw_page_id")
            unchanged = bool(result.get("unchanged", False))
            excluded = bool(result.get("excluded", False))
            fetched_count = 1
            raw_page_inserted = 0 if unchanged else 1
            sections_created = len(result.get("section_ids") or [])
            ac_embeddings_created = int(result.get("indexed_count") or 0)
            ec_embeddings_created = 0
            evidence_created = 0

            # Avoid duplicate evidence rows when content is unchanged.
            if raw_page_id and not unchanged and not excluded:
                ec_result = index_ec(tenant_id, int(raw_page_id))
                ec_embeddings_created = int(ec_result.get("indexed_ec_count") or 0)
                evidence_created = int(ec_result.get("evidence_count") or 0)

            summary = {
                "tenant_id": tenant_id,
                "domain": normalized_domain,
                "url": url,
                "fetched_count": fetched_count,
                "raw_page_inserted": raw_page_inserted,
                "sections_created": sections_created,
                "ac_embeddings_created": ac_embeddings_created,
                "ec_embeddings_created": ec_embeddings_created,
                "evidence_created": evidence_created,
                "excluded": excluded,
                "unchanged": unchanged,
            }
            logger.info(
                "ingest_done tenant_id=%s domain=%s fetched_count=%s raw_page_inserted=%s "
                "sections_created=%s embeddings_created=%s",
                tenant_id,
                normalized_domain,
                fetched_count,
                raw_page_inserted,
                sections_created,
                ac_embeddings_created + ec_embeddings_created,
            )
            logger.info(
                "ingest_stats tenant_id=%s domain=%s ac_embeddings_created=%s ec_embeddings_created=%s evidence_created=%s",
                tenant_id,
                normalized_domain,
                ac_embeddings_created,
                ec_embeddings_created,
                evidence_created,
            )
            return summary
        except Exception as exc:
            last_error = exc
            logger.warning(
                "ingest_attempt_failed tenant_id=%s domain=%s url=%s error=%s",
                tenant_id,
                normalized_domain,
                url,
                str(exc),
            )
            continue

    raise RuntimeError(
        f"ingest failed for domain={normalized_domain}: {last_error}" if last_error else f"ingest failed for domain={normalized_domain}"
    )
