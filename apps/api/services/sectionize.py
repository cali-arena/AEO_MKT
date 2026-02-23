"""Sectionizer v1: heading-based extraction + paragraph fallback, stable section_id/hashes."""

import hashlib
import logging
import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString, PageElement, Tag

from apps.api.services.repo import _assert_tenant, delete_sections_for_raw_page, get_raw_page_metadata, insert_sections
from apps.api.services.section_norm import normalize_for_id, sha256_hex

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1050
OVERLAP = 150

# For paragraph fallback
FALLBACK_CHUNK_MIN = 1200
FALLBACK_CHUNK_MAX = 1600
FALLBACK_OVERLAP = 150
HEADING_TAGS = ["h1", "h2", "h3"]
MIN_HEADING_SECTIONS = 2  # if heading extraction yields fewer, use fallback


def sectionize(html: str | None, text: str, canonical_url: str) -> list[dict[str, str]]:
    """
    Extract sections from html/text. Returns list of {heading_path, section_text}.
    Strategy 1: parse html, walk h1/h2/h3, collect text until next heading of same/higher level.
    Strategy 2: fallback - chunk text by paragraphs (split by blank lines, ~1200-1600 chars, 150 overlap).
    """
    sections = _sectionize_from_headings(html) if html else []
    if len(sections) < MIN_HEADING_SECTIONS:
        sections = _sectionize_fallback(text)
    return sections


def _sectionize_from_headings(html: str) -> list[dict[str, str]]:
    """Walk h1/h2/h3 in document order, collect text until next heading of same or higher level."""
    soup = BeautifulSoup(html, "html.parser")
    sections: list[dict[str, str]] = []
    heading_stack: list[tuple[int, str]] = []  # (level 1-3, heading text)

    def level(tag: Tag) -> int:
        m = re.match(r"h(\d)", tag.name or "")
        return int(m.group(1)) if m else 0

    def get_text_before_heading(el: PageElement) -> str:
        """Get text from element, stopping at any descendant heading."""
        if isinstance(el, NavigableString):
            return str(el).strip()
        if isinstance(el, Tag) and el.name in HEADING_TAGS:
            return ""
        parts: list[str] = []
        for child in getattr(el, "children", []) or []:
            if isinstance(child, Tag) and child.name in HEADING_TAGS:
                break
            parts.append(get_text_before_heading(child))
        return " ".join(p for p in parts if p)

    def text_up_to(next_sibling: PageElement | None) -> str:
        parts: list[str] = []
        sib = next_sibling
        while sib:
            if isinstance(sib, NavigableString):
                parts.append(str(sib).strip())
            elif isinstance(sib, Tag):
                if sib.name in HEADING_TAGS:
                    break
                parts.append(get_text_before_heading(sib))
            sib = sib.next_sibling
            if sib and isinstance(sib, Tag) and sib.name in HEADING_TAGS:
                break
        return " ".join(p for p in parts if p)

    for tag in soup.find_all(HEADING_TAGS):
        if not isinstance(tag, Tag):
            continue
        lvl = level(tag)
        heading_text = tag.get_text(strip=True)
        while heading_stack and heading_stack[-1][0] >= lvl:
            heading_stack.pop()
        heading_stack.append((lvl, heading_text))
        path = " > ".join(h for _, h in heading_stack)

        content = text_up_to(tag.next_sibling)
        if content or heading_text:
            sections.append({"heading_path": path, "section_text": (heading_text + " " + content).strip() or heading_text})

    return sections


def _sectionize_fallback(text: str) -> list[dict[str, str]]:
    """Chunk by paragraphs: split by blank lines, accumulate ~1200-1600 chars, 150 overlap."""
    if not text.strip():
        return []
    paras = re.split(r"\n\s*\n", text)
    paras = [p.strip() for p in paras if p.strip()]
    if not paras:
        return [{"heading_path": "", "section_text": text.strip()}]

    chunks: list[str] = []
    acc: list[str] = []
    acc_len = 0
    for p in paras:
        p_len = len(p) + 2
        if acc_len + p_len > FALLBACK_CHUNK_MAX and acc:
            chunk_text = "\n\n".join(acc)
            chunks.append(chunk_text)
            overlap_paras: list[str] = []
            overlap_len = 0
            for x in reversed(acc):
                if overlap_len + len(x) > FALLBACK_OVERLAP:
                    break
                overlap_paras.insert(0, x)
                overlap_len += len(x) + 2
            acc = overlap_paras
            acc_len = overlap_len
        acc.append(p)
        acc_len += p_len

    if acc:
        chunks.append("\n\n".join(acc))

    return [{"heading_path": "", "section_text": c} for c in chunks]


def _compute_version_hash(section_id: str, section_hash: str, raw_page_version: int) -> str:
    """version_hash = sha256(section_id|section_hash|raw_page_version)[:12]. Changes when raw_page.version increments."""
    payload = section_id + "|" + section_hash + "|" + str(raw_page_version)
    return sha256_hex(payload)[:12]


def _build_section_records(
    sections: list[dict[str, str]],
    canonical_url: str,
    raw_page_version: int,
    *,
    raw_page_content_hash: str = "",
) -> list[dict[str, Any]]:
    """Convert sectionize output to full section records with stable ids and hashes.
    raw_page_version: included in version_hash so it changes when raw_page.version increments."""
    out: list[dict[str, Any]] = []
    for sec in sections:
        text = sec["section_text"]
        heading_path = sec.get("heading_path", "")
        normalized = normalize_for_id(text)
        section_hash = sha256_hex(normalized)
        section_id = sha256_hex(canonical_url + "|" + heading_path + "|" + normalized)[:24]
        version_hash = _compute_version_hash(section_id, section_hash, raw_page_version)
        out.append({
            "section_id": section_id,
            "heading_path": heading_path,
            "text": text,
            "start_char": 0,
            "end_char": len(text),
            "section_hash": section_hash,
            "version_hash": version_hash,
        })
    return out


def _chunk_text(full_text: str) -> list[tuple[int, int, str]]:
    """Split full_text into overlapping chunks. Returns [(start_char, end_char, chunk_text), ...]."""
    if not full_text:
        return []
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(full_text):
        end = min(start + CHUNK_SIZE, len(full_text))
        chunk_text = full_text[start:end]
        chunks.append((start, end, chunk_text))
        if end >= len(full_text):
            break
        start = end - OVERLAP
    return chunks


def _section_id(canonical_url: str, chunk_index: int) -> str:
    """Stable section_id: position-based, does NOT depend on chunk text.
    section_id = sec_ + sha1(canonical_url + ':' + str(chunk_index))[:16]
    """
    payload = canonical_url + ":" + str(chunk_index)
    h = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return "sec_" + h


def compute_section_ids(url: str, full_text: str) -> list[str]:
    """Pure, deterministic: same URL + same chunking => same section_ids. Used for stability tests."""
    chunks = _chunk_text(full_text)
    return [_section_id(url, i) for i in range(len(chunks))]


def compute_section_metadata(url: str, full_text: str) -> list[dict[str, Any]]:
    """Pure: compute section_id, version_hash, section_hash per chunk. For tests."""
    chunks = _chunk_text(full_text)
    out: list[dict[str, Any]] = []
    for i, (start_char, end_char, chunk_text) in enumerate(chunks):
        section_hash_val = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        version_hash_val = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        out.append({
            "section_id": _section_id(url, i),
            "version_hash": version_hash_val,
            "section_hash": section_hash_val,
        })
    return out


def sectionize_and_persist(
    tenant_id: str | None,
    raw_page_id: int,
    url: str,
    full_text: str,
    *,
    html: str | None = None,
    raw_page_content_hash: str = "",
    domain: str | None = None,
    page_type: str | None = None,
    crawl_policy_version: str | None = None,
) -> list[str]:
    """
    Extract sections via sectionize(html, text, url), compute stable section_id/hashes, insert.
    raw_page_content_hash: content_hash from ingest (for version_hash).
    """
    _assert_tenant(tenant_id)
    meta = get_raw_page_metadata(tenant_id, raw_page_id)
    if domain is None:
        domain = meta.get("domain")
    if page_type is None:
        page_type = meta.get("page_type")
    if crawl_policy_version is None:
        crawl_policy_version = meta.get("crawl_policy_version")

    sections = sectionize(html, full_text, url)
    if not sections:
        logger.info("sectionize url=%s raw_page_id=%s sections=0", url, raw_page_id)
        return []

    delete_sections_for_raw_page(tenant_id, raw_page_id)
    raw_page_version = meta.get("version", 1) or 1
    records = _build_section_records(sections, url, raw_page_version)
    for r in records:
        r["domain"] = domain
        r["page_type"] = page_type
        r["crawl_policy_version"] = crawl_policy_version

    insert_sections(tenant_id, raw_page_id, records)
    section_ids = [r["section_id"] for r in records]
    logger.info("sectionize url=%s raw_page_id=%s sections=%d ids=%s", url, raw_page_id, len(section_ids), section_ids[:3])
    return section_ids
