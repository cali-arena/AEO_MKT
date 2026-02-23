"""Evidence mapping enforcement. Deterministic evidence_id from retrieval results."""

import hashlib
from typing import Any


def _evidence_id(tenant_id: str, section_id: str, url: str, quote_span: str) -> str:
    """Deterministic evidence_id from content. Same inputs → same id."""
    data = f"{tenant_id}:{section_id}:{url}:{quote_span}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:32]


def build_evidence_map(
    tenant_id: str,
    retrieval_results: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Build evidence_id -> {tenant_id, url, section_id, quote_span} from retrieval results.

    retrieval_results: list of {section_id, url, quote_span} (quote_span required).
    evidence_id is deterministic from tenant_id + section_id + url + quote_span.
    Duplicate (section_id, url, quote_span) deduplicated to single entry.
    """
    out: dict[str, dict[str, Any]] = {}
    for r in retrieval_results:
        section_id = r.get("section_id") or ""
        url = r.get("url") or ""
        quote_span = r.get("quote_span") or ""
        eid = _evidence_id(tenant_id, section_id, url, quote_span)
        out[eid] = {
            "tenant_id": tenant_id,
            "url": url,
            "section_id": section_id,
            "quote_span": quote_span,
        }
    return out


def evidence_records_for_insert(
    tenant_id: str,
    retrieval_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build list of evidence records for insert_evidence from retrieval results.
    retrieval_results: [{section_id, url, quote_span, start_char, end_char, version_hash}, ...]
    Returns [{evidence_id, section_id, url, quote_span, start_char, end_char, version_hash}, ...]
    """
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in retrieval_results:
        section_id = r.get("section_id") or ""
        url = r.get("url") or ""
        quote_span = r.get("quote_span") or ""
        eid = _evidence_id(tenant_id, section_id, url, quote_span)
        if eid in seen:
            continue
        seen.add(eid)
        records.append({
            "evidence_id": eid,
            "section_id": section_id,
            "url": url,
            "quote_span": quote_span,
            "start_char": r.get("start_char"),
            "end_char": r.get("end_char"),
            "version_hash": r.get("version_hash"),
        })
    return records
