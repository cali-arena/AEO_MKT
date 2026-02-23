"""Ingest: extract text, compute hash, persist to raw_page."""

import logging
from datetime import datetime
from typing import Any

from apps.api.services.extract import extract_main_text
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
