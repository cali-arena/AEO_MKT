"""Day 1 pipeline: crawl -> ingest -> sectionize -> index_ac."""

import argparse
import logging
import sys
from datetime import datetime
from typing import Any

from apps.api.services.crawl import fetch_html_with_meta

# Stable ordered stages for deterministic pipeline execution (no set/dict iteration).
# Patch target for tests: patch apps.api.services.pipeline._fetch (where pipeline imports it).
PIPELINE_STAGES = (
    "url_exclusion",
    "domain_gate",
    "fetch",
    "extract",
    "content_exclusion",
    "ingest",
    "sectionize",
    "index_ac",
)


def _fetch(url: str) -> dict[str, Any]:
    """Wrapper for fetch_html_with_meta; patch this in tests."""
    return fetch_html_with_meta(url)
from apps.api.services.extract import extract_main_text, extract_title
from apps.api.services.normalize import content_hash, normalize_text
from apps.api.services.crawl_report import write_crawl_record
from apps.api.services.exclusion import PAGE_TYPE_EXCLUDED, should_exclude
from apps.api.services.index_ac import index_ac
from apps.api.services.ingest import ingest_page
from apps.api.services.page_type import infer_page_type
from apps.api.services.policy import crawl_policy_version as get_crawl_policy_version
from apps.api.services.policy import load_policy
from apps.api.services.repo import (
    delete_ac_embeddings_for_section_ids,
    delete_ec_embeddings_for_section_ids,
    get_artifact_counts_for_raw_page,
    get_sections_by_raw_page_id,
    insert_raw_page,
    list_eval_domains,
)
from apps.api.services.sectionize import sectionize_and_persist
from apps.api.services.url_utils import canonicalize_url

logger = logging.getLogger(__name__)


def _store_excluded_raw_page(
    tenant_id: str,
    canonical_url: str,
    domain: str,
    reason: str,
    *,
    html: str | None = None,
    text: str | None = None,
    status_code: int | None = None,
    fetched_at: datetime | None = None,
) -> None:
    """Insert excluded raw_page and append to crawl_report."""
    policy = load_policy()
    policy_ver = get_crawl_policy_version(policy)
    ch = content_hash(text) if text else None

    insert_raw_page(
        tenant_id,
        url=canonical_url,
        canonical_url=canonical_url,
        html=html,
        text=text,
        status_code=status_code,
        content_hash=ch,
        domain=domain,
        page_type=PAGE_TYPE_EXCLUDED,
        crawl_policy_version=policy_ver,
        crawl_decision="excluded",
        crawl_reason=reason,
        fetched_at=fetched_at,
    )
    write_crawl_record(
        tenant_id=tenant_id,
        url=canonical_url,
        canonical_url=canonical_url,
        domain=domain,
        page_type=PAGE_TYPE_EXCLUDED,
        decision="excluded",
        reason=reason,
    )


def run_day1_pipeline(
    tenant_id: str,
    url: str,
) -> dict[str, Any]:
    """
    Run full Day 1 pipeline: crawl, ingest, sectionize, index_ac.
    Flow: canonicalize -> should_exclude(url) [exclusion wins] -> domain gate -> fetch -> should_exclude(url,html,text) -> ingest -> sectionize -> index_ac.
    """
    logger.info("Day1 pipeline start tenant_id=%s url=%s", tenant_id, url)

    canonical_url, domain = canonicalize_url(url)

    # 1) URL-only exclusion (before domain gate; exclusion wins for proof/logging)
    excluded, reason, _ = should_exclude(url, html=None, text=None)
    if excluded:
        logger.info("Day1 pipeline excluded by URL url=%s reason=%s", url, reason)
        _store_excluded_raw_page(tenant_id, canonical_url, domain, reason)
        return {"excluded": True, "reason": reason, "url": url, "page_type": PAGE_TYPE_EXCLUDED}

    # 2) Enforce allowed domain: policy allowed_domains OR tenant's registered eval domains (so Evaluate works for added domains)
    policy = load_policy()
    policy_allowed = [d.strip().lower() for d in policy.get("allowed_domains", []) if d]
    registered = [d.strip().lower() for d in list_eval_domains(tenant_id) if d]
    allowed_set = set(policy_allowed) | set(registered)
    domain_normalized = (domain or "").strip().lower()
    if domain_normalized and domain_normalized not in allowed_set:
        logger.info(
            "Day1 pipeline domain not allowed url=%s domain=%s allowed_policy=%s allowed_registered=%s",
            url,
            domain_normalized,
            sorted(policy_allowed),
            sorted(registered),
        )
        raise ValueError("domain_not_allowed")
    if domain_normalized and allowed_set:
        logger.info("Day1 pipeline domain allowed url=%s domain=%s", url, domain_normalized)

    # 3) Fetch
    fetch_result = _fetch(url)
    html = fetch_result["html"]
    final_url = fetch_result["final_url"]
    final_canonical, final_domain = canonicalize_url(final_url)

    # 4) Extract -> normalize -> hash -> title
    main_text = extract_main_text(html)
    normalized = normalize_text(main_text)
    ch = content_hash(normalized)
    title = extract_title(html)

    # 5) Full exclusion (with html/text)
    excluded, reason, _ = should_exclude(final_url, html=html, text=normalized)
    if excluded:
        logger.info("Day1 pipeline excluded by content url=%s reason=%s", url, reason)
        _store_excluded_raw_page(
            tenant_id,
            final_canonical,
            final_domain,
            reason,
            html=html,
            text=normalized,
            status_code=fetch_result.get("status_code"),
            fetched_at=fetch_result.get("fetched_at"),
        )
        return {"excluded": True, "reason": reason, "url": url, "page_type": PAGE_TYPE_EXCLUDED}

    # 6) Infer page_type, ingest
    page_type = infer_page_type(final_url, title=title, text=normalized)
    policy_ver = get_crawl_policy_version(policy)

    write_crawl_record(
        tenant_id=tenant_id,
        url=url,
        canonical_url=final_canonical,
        domain=final_domain,
        page_type=page_type,
        decision="allowed",
        reason="",
    )

    ingest_result = ingest_page(
        tenant_id,
        url,
        {**fetch_result, "final_url": final_url},
        domain=final_domain,
        page_type=page_type,
        crawl_policy_version=policy_ver,
        crawl_decision="allowed",
        crawl_reason="",
        extracted_text=normalized,
        precomputed_content_hash=ch,
    )
    raw_page_id = ingest_result["raw_page_id"]
    unchanged = ingest_result.get("unchanged", False)

    if unchanged:
        sections_count, ac_count, ec_count = get_artifact_counts_for_raw_page(tenant_id, raw_page_id)
        logger.info(
            "raw_page unchanged url=%s raw_page_id=%s artifact_check sections=%d ac=%d ec=%d",
            url,
            raw_page_id,
            sections_count,
            ac_count,
            ec_count,
        )
        sections_missing = sections_count == 0
        embeddings_missing = ac_count == 0 or ec_count == 0
        if sections_missing or embeddings_missing:
            logger.info(
                "unchanged_but_missing -> rebuilding sectionize+embeddings url=%s raw_page_id=%s",
                url,
                raw_page_id,
            )
            section_ids = sectionize_and_persist(
                tenant_id,
                raw_page_id,
                final_url,
                normalized,
                html=html,
                raw_page_content_hash=ch,
                domain=final_domain,
                page_type=page_type,
                crawl_policy_version=policy_ver,
            )
            sections = get_sections_by_raw_page_id(tenant_id, raw_page_id)
            if not sections:
                logger.info("Day1 pipeline no sections url=%s (rebuild)", url)
                return {"raw_page_id": raw_page_id, "section_ids": [], "indexed_count": 0, "evidence_ids": [], "unchanged": False}
            delete_ac_embeddings_for_section_ids(tenant_id, section_ids)
            delete_ec_embeddings_for_section_ids(tenant_id, section_ids)
            sections_for_ac = [
                {
                    "section_id": s["section_id"],
                    "text": s["text"],
                    "version_hash": s["version_hash"],
                    "url": final_url,
                    "domain": s.get("domain") or "",
                }
                for s in sections
            ]
            indexed_count = index_ac(tenant_id, sections_for_ac)
            logger.info("Day1 pipeline done (repaired) url=%s raw_page_id=%s sections=%d", url, raw_page_id, len(section_ids))
            return {
                "raw_page_id": raw_page_id,
                "section_ids": section_ids,
                "indexed_count": indexed_count,
                "evidence_ids": [],
                "unchanged": False,
            }
        logger.info("Day1 pipeline unchanged url=%s raw_page_id=%s skipping re-sectionize", url, raw_page_id)
        return {
            "raw_page_id": raw_page_id,
            "section_ids": [],
            "indexed_count": 0,
            "evidence_ids": [],
            "unchanged": True,
        }

    section_ids = sectionize_and_persist(
        tenant_id,
        raw_page_id,
        final_url,
        normalized,
        html=html,
        raw_page_content_hash=ch,
        domain=final_domain,
        page_type=page_type,
        crawl_policy_version=policy_ver,
    )
    sections = get_sections_by_raw_page_id(tenant_id, raw_page_id)
    if not sections:
        logger.info("Day1 pipeline no sections url=%s", url)
        return {"raw_page_id": raw_page_id, "section_ids": [], "indexed_count": 0, "evidence_ids": []}

    sections_for_ac = [
        {
            "section_id": s["section_id"],
            "text": s["text"],
            "version_hash": s["version_hash"],
            "url": final_url,
            "domain": s.get("domain") or "",
        }
        for s in sections
    ]
    indexed_count = index_ac(tenant_id, sections_for_ac)

    logger.info("Day1 pipeline done url=%s raw_page_id=%s sections=%d", url, raw_page_id, len(section_ids))
    return {
        "raw_page_id": raw_page_id,
        "section_ids": section_ids,
        "indexed_count": indexed_count,
        "evidence_ids": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Day 1 pipeline: crawl, ingest, sectionize, index_ac"
    )
    parser.add_argument("--tenant", required=True, help="Tenant ID")
    parser.add_argument("--url", required=True, help="URL to crawl")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = run_day1_pipeline(args.tenant, args.url)
    if result.get("excluded"):
        print(f"Excluded URL (reason={result.get('reason', '')})")
        sys.exit(0)
    print(result)


if __name__ == "__main__":
    main()
