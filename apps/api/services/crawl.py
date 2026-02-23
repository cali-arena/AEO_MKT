"""Day 1 Crawler v1. Single URL fetch, no recursion."""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

from apps.api.services.crawl_rules import classify_url, is_url_allowed
from apps.api.services.extract import extract_main_text
from apps.api.services.normalize import content_hash
from apps.api.services.policy import crawl_policy_version as get_crawl_policy_version
from apps.api.services.policy import load_policy
from apps.api.services.repo import insert_raw_page
from apps.api.services.url_utils import canonicalize_url

BACKOFF_SECONDS = (0.5, 1, 2)


def crawl_and_persist(tenant_id: str, url: str) -> dict[str, Any]:
    """
    Crawl URL and persist to raw_page.
    Flow: canonicalize -> domain gate -> fetch_html -> extract_main_text -> content_hash -> insert_raw_page.
    Returns {raw_page_id, canonical_url, domain, page_type, crawl_policy_version, content_hash}.
    Raises ValueError("domain_not_allowed") if domain not in policy.
    """
    canonical_url, domain = canonicalize_url(url)
    policy = load_policy()
    allowed_domains = policy.get("allowed_domains", [])
    if domain and domain not in allowed_domains:
        raise ValueError("domain_not_allowed")

    html = fetch_html(url)
    text = extract_main_text(html)
    ch = content_hash(text)
    _, page_type, _ = classify_url(url)
    policy_ver = get_crawl_policy_version(policy)

    raw_page_id = insert_raw_page(
        tenant_id,
        url=canonical_url,
        canonical_url=canonical_url,
        text=text,
        content_hash=ch,
        domain=domain,
        page_type=page_type,
        crawl_policy_version=policy_ver,
    )
    return {
        "raw_page_id": raw_page_id,
        "canonical_url": canonical_url,
        "domain": domain,
        "page_type": page_type,
        "crawl_policy_version": policy_ver,
        "content_hash": ch,
    }


def fetch_html(url: str) -> str:
    """
    Fetch HTML from a single URL. No recursion.
    - 3 retries with exponential backoff (0.5, 1, 2) seconds
    - timeout 10s
    - only accepts content-type containing text/html; raises otherwise
    """
    last_exc: Exception | None = None
    for attempt, delay in enumerate(BACKOFF_SECONDS):
        try:
            resp = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "AI-MKT-Crawler/1.0"},
                allow_redirects=True,
            )
            content_type = resp.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                raise ValueError(f"content_type_not_html: {content_type}")
            return resp.text
        except (requests.RequestException, ValueError) as e:
            last_exc = e
            if attempt < len(BACKOFF_SECONDS) - 1:
                time.sleep(delay)
    raise last_exc


def fetch_html_with_meta(url: str) -> dict[str, Any]:
    """
    Fetch HTML and return {html, final_url, status_code, fetched_at}.
    Same retry/backoff/content-type rules as fetch_html.
    """
    last_exc: Exception | None = None
    for attempt, delay in enumerate(BACKOFF_SECONDS):
        try:
            resp = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "AI-MKT-Crawler/1.0"},
                allow_redirects=True,
            )
            content_type = resp.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                raise ValueError(f"content_type_not_html: {content_type}")
            return {
                "html": resp.text,
                "final_url": resp.url,
                "status_code": resp.status_code,
                "fetched_at": datetime.now(timezone.utc),
            }
        except (requests.RequestException, ValueError) as e:
            last_exc = e
            if attempt < len(BACKOFF_SECONDS) - 1:
                time.sleep(delay)
    raise last_exc


logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_USER_AGENT = "AI-MKT-Crawler/1.0"


def fetch_url(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Any]:
    """
    Fetch a single URL. No recursion.
    Returns {final_url, status_code, html, fetched_at} on success, or
    {excluded: True, reason: str, url: str} when excluded by crawl rules.
    Raises ValueError("domain_not_allowed") if domain not in policy allowed_domains.
    """
    allowed, reason = is_url_allowed(url)
    if not allowed:
        logger.info("EXCLUDED url=%s reason=%s", url, reason)
        return {"excluded": True, "reason": reason, "url": url}

    _, domain = canonicalize_url(url)
    policy = load_policy()
    allowed_domains = policy.get("allowed_domains", [])
    if domain and domain not in allowed_domains:
        raise ValueError("domain_not_allowed")

    logger.info("Fetching url=%s", url)
    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": user_agent},
        allow_redirects=True,
    )
    html = resp.text
    final_url = resp.url
    fetched_at = datetime.now(timezone.utc)
    logger.info("Fetched url=%s final_url=%s status=%s", url, final_url, resp.status_code)
    return {
        "final_url": final_url,
        "status_code": resp.status_code,
        "html": html,
        "fetched_at": fetched_at,
    }
