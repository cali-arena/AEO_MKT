"""EC extraction v1: entities and relations from sections, linked to evidence."""

import hashlib
import logging
import re
import uuid
from collections.abc import Callable
from typing import Any

from apps.api.services.ec_extract import extract_entities, make_entity_id
from apps.api.services.embedding_provider import embed_texts
from apps.api.services.repo import (
    _assert_tenant,
    delete_ec_embeddings_for_tenant,
    delete_entity_mentions_for_tenant,
    get_raw_page_url,
    get_sections_by_raw_page_id,
    get_sections_for_tenant,
    insert_ec_embeddings,
    insert_entity_mentions,
    insert_evidence,
    insert_relation,
    upsert_ec_version,
    upsert_entity,
)

logger = logging.getLogger(__name__)

# Service phrase list for regex fallback
SERVICE_PHRASES = [
    "long distance",
    "local moving",
    "commercial moving",
    "packing",
    "storage",
    "residential moving",
    "interstate moving",
]

# US state abbreviations (common)
STATE_ABBREVS = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
)

DEFAULT_COMPANY_NAME = "Coast to Coast Movers"
DEFAULT_COMPANY_TYPE = "ORG"

_spacy_nlp = None


def _get_spacy():
    """Load spaCy NER model if available."""
    global _spacy_nlp
    if _spacy_nlp is not None:
        return _spacy_nlp
    try:
        import spacy
        _spacy_nlp = spacy.load("en_core_web_sm")
        return _spacy_nlp
    except (ImportError, OSError):
        return None


def _normalize_name(name: str) -> str:
    """Strip, collapse spaces."""
    return re.sub(r"\s+", " ", name.strip())


def _entity_id(tenant_id: str, norm_name: str, entity_type: str) -> str:
    """Stable entity_id: ent_ + sha1(tenant_id:norm_name:type)[:16]."""
    payload = f"{tenant_id}:{norm_name}:{entity_type}"
    h = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return "ent_" + h


def _split_sentences(text: str) -> list[tuple[int, int, str]]:
    """Split into sentences. Returns [(start, end, sentence), ...]."""
    if not text.strip():
        return []
    parts = re.split(r"(?<=[.?!])\s+|\n+", text)
    pos = 0
    out = []
    for s in parts:
        s = s.strip()
        if not s:
            continue
        start = text.find(s, pos)
        if start < 0:
            start = pos
        end = start + len(s)
        out.append((start, end, s))
        pos = end
    return out


def _extract_with_spacy(text: str) -> list[tuple[str, str, int, int]]:
    """Extract (text, label, start, end) using spaCy NER."""
    nlp = _get_spacy()
    if nlp is None:
        return []
    doc = nlp(text)
    out = []
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC", "FAC", "ORG", "PERSON", "PRODUCT"):
            out.append((ent.text, ent.label_, ent.start_char, ent.end_char))
    return out


def _extract_with_regex(text: str) -> list[tuple[str, str, int, int]]:
    """Fallback: regex for locations, phone, services. Returns (match_text, type, start, end)."""
    out = []
    seen = set()

    # (City, ST) pattern - 1-3 capitalized words (e.g. Dallas, TX; New York, NY)
    city_state = re.compile(
        r"([A-Z][a-zA-Z\-\.]*(?:\s+[A-Z][a-zA-Z\-\.]*){0,2}),\s*(" + "|".join(STATE_ABBREVS) + r")\b",
    )
    for m in city_state.finditer(text):
        key = (m.start(), "LOC")
        if key not in seen:
            seen.add(key)
            out.append((m.group(0), "LOC", m.start(), m.end()))

    # Standalone state abbreviation (optional)
    state_only = re.compile(r"\b(" + "|".join(STATE_ABBREVS) + r")\b")
    for m in state_only.finditer(text):
        key = (m.start(), "LOC")
        if key not in seen:
            seen.add(key)
            out.append((m.group(1), "LOC", m.start(), m.end()))

    # Phone
    phone = re.compile(r"\+?\d[\d\-\(\) ]{7,}")
    for m in phone.finditer(text):
        key = (m.start(), "PHONE")
        if key not in seen:
            seen.add(key)
            out.append((m.group(0), "PHONE", m.start(), m.end()))

    # Services (case-insensitive)
    text_lower = text.lower()
    for phrase in SERVICE_PHRASES:
        start = 0
        while True:
            idx = text_lower.find(phrase, start)
            if idx < 0:
                break
            end = idx + len(phrase)
            # Extract actual span from original text
            span = text[idx:end]
            key = (idx, "SERVICE")
            if key not in seen:
                seen.add(key)
                out.append((span, "SERVICE", idx, end))
            start = end

    return out


def extract_entities_and_relations(
    tenant_id: str,
    section_text: str,
    section_id: str,
    url: str,
    version_hash: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Extract entities and relations from section text.
    Returns (entities, evidence_list, relations).
    Each entity: {entity_id, name, type, section_id, evidence_id}
    Each evidence: {evidence_id, section_id, url, quote_span, start_char, end_char, version_hash}
    Each relation: {subject_entity_id, predicate, object_entity_id, evidence_id}
    """
    entities_out = []
    evidence_out = []
    relations_out = []
    entity_id_to_evidence = {}

    mentions = _extract_with_spacy(section_text)
    if not mentions:
        mentions = _extract_with_regex(section_text)

    for match_text, entity_type, start, end in mentions:
        norm = _normalize_name(match_text)
        if not norm:
            continue
        eid = _entity_id(tenant_id, norm.lower(), entity_type)

        evidence_id = str(uuid.uuid4())
        quote_span = section_text[start:end]
        evidence_out.append({
            "evidence_id": evidence_id,
            "section_id": section_id,
            "url": url,
            "quote_span": quote_span,
            "start_char": start,
            "end_char": end,
            "version_hash": version_hash,
        })
        entity_id_to_evidence[eid] = evidence_id

        entities_out.append({
            "entity_id": eid,
            "name": norm,
            "type": entity_type,
            "section_id": section_id,
            "evidence_id": evidence_id,
        })

    company_id = _entity_id(tenant_id, DEFAULT_COMPANY_NAME.lower(), DEFAULT_COMPANY_TYPE)
    company_evidence_id = None
    sentences = _split_sentences(section_text)
    if sentences:
        start, end, sent = sentences[0]
        company_evidence_id = str(uuid.uuid4())
        evidence_out.append({
            "evidence_id": company_evidence_id,
            "section_id": section_id,
            "url": url,
            "quote_span": sent[:280],
            "start_char": start,
            "end_char": min(end, start + 280),
            "version_hash": version_hash,
        })

    entities_out.append({
        "entity_id": company_id,
        "name": DEFAULT_COMPANY_NAME,
        "type": DEFAULT_COMPANY_TYPE,
        "section_id": section_id,
        "evidence_id": company_evidence_id,
    })

    rel_evidence_id = company_evidence_id
    if not rel_evidence_id and evidence_out:
        rel_evidence_id = evidence_out[0]["evidence_id"]

    for e in entities_out:
        if e["entity_id"] == company_id:
            continue
        etype = e.get("type") or ""
        if etype == "SERVICE":
            relations_out.append({
                "subject_entity_id": company_id,
                "predicate": "SERVICE_OFFERED",
                "object_entity_id": e["entity_id"],
                "evidence_id": rel_evidence_id,
            })
        elif etype in ("LOC", "GPE", "FAC"):
            relations_out.append({
                "subject_entity_id": company_id,
                "predicate": "SERVES_LOCATION",
                "object_entity_id": e["entity_id"],
                "evidence_id": rel_evidence_id,
            })

    return (entities_out, evidence_out, relations_out)


def build_ec(
    tenant_id: str | None,
    *,
    embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
) -> dict[str, Any]:
    """
    Build Entity Corpus from all tenant sections. Idempotent v1.

    For a given tenant_id:
    - Load all sections (tenant-scoped)
    - Run extraction per section via ec_extract.extract_entities
    - Create entities + mentions
    - Upsert entities by (tenant_id, entity_id)
    - Rebuild mentions idempotently: delete existing, insert fresh
    - Compute/store ec_embeddings (canonical string per entity)
    - Store ec_version_hash for tenant

    embed_fn: injectable embedding function. Defaults to embed_texts (uses provider).
    Use a mock in tests to avoid network.
    """
    _assert_tenant(tenant_id)

    sections = get_sections_for_tenant(tenant_id)
    if not sections:
        logger.info("build_ec tenant_id=%s no sections", tenant_id)
        upsert_ec_version(tenant_id, "")
        return {
            "entities_count": 0,
            "mentions_count": 0,
            "indexed_ec_count": 0,
            "ec_version_hash": "",
        }

    # Extract per section
    entities_map: dict[str, dict[str, Any]] = {}  # entity_id -> {entity_id, canonical_name, type}
    mentions: list[dict[str, Any]] = []

    for s in sections:
        section_id = s["section_id"]
        text = s.get("text") or ""
        extracted = extract_entities(text)
        for m in extracted:
            entity_id = make_entity_id(tenant_id, m.entity_type, m.canonical_name)
            entities_map[entity_id] = {
                "entity_id": entity_id,
                "canonical_name": m.canonical_name,
                "type": m.entity_type,
            }
            mentions.append({
                "entity_id": entity_id,
                "section_id": section_id,
                "start_offset": m.start_offset,
                "end_offset": m.end_offset,
                "quote_span": m.quote_span,
                "confidence": m.confidence,
            })

    # Upsert entities
    for ent in entities_map.values():
        upsert_entity(tenant_id, {
            "entity_id": ent["entity_id"],
            "canonical_name": ent["canonical_name"],
            "type": ent["type"],
        })

    # Rebuild mentions idempotently: delete existing, insert fresh
    delete_entity_mentions_for_tenant(tenant_id)
    insert_entity_mentions(tenant_id, mentions)

    # Embed canonical strings and store
    delete_ec_embeddings_for_tenant(tenant_id)
    canonical_strings = [e["canonical_name"] or "" for e in entities_map.values()]
    fn = embed_fn if embed_fn is not None else embed_texts
    embeddings = fn(canonical_strings)
    records = [
        {"entity_id": eid, "embedding": embeddings[i]}
        for i, eid in enumerate(entities_map)
    ]
    insert_ec_embeddings(tenant_id, records)

    # Compute and store ec_version_hash
    section_sigs = "|".join(sorted(f"{s['section_id']}:{s.get('version_hash', '')}" for s in sections))
    entity_sigs = "|".join(sorted(entities_map.keys()))
    payload = f"{section_sigs}||{entity_sigs}"
    ec_version_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    upsert_ec_version(tenant_id, ec_version_hash)

    logger.info(
        "build_ec tenant_id=%s entities=%d mentions=%d ec_version_hash=%s",
        tenant_id, len(entities_map), len(mentions), ec_version_hash,
    )
    return {
        "entities_count": len(entities_map),
        "mentions_count": len(mentions),
        "indexed_ec_count": len(records),
        "ec_version_hash": ec_version_hash,
    }


def index_ec(tenant_id: str | None, raw_page_id: int) -> dict[str, Any]:
    """
    Load sections for raw_page_id, extract entities/relations, store and index.
    Returns {entities_count, relations_count, evidence_count, indexed_ec_count}.
    """
    _assert_tenant(tenant_id)

    sections = get_sections_by_raw_page_id(tenant_id, raw_page_id)
    if not sections:
        logger.info("index_ec tenant_id=%s raw_page_id=%s no sections", tenant_id, raw_page_id)
        return {"entities_count": 0, "relations_count": 0, "evidence_count": 0, "indexed_ec_count": 0}

    url = get_raw_page_url(tenant_id, raw_page_id) or "https://example.com"
    entities_count = 0
    relations_count = 0
    evidence_count = 0
    entities_to_embed = []
    seen_entity_ids = set()

    for s in sections:
        section_id = s["section_id"]
        text = s.get("text") or ""
        version_hash = s.get("version_hash") or ""

        entities, evidence_list, relations = extract_entities_and_relations(
            tenant_id, text, section_id, url, version_hash
        )

        for ev in evidence_list:
            insert_evidence(tenant_id, [ev])
            evidence_count += 1

        for ent in entities:
            upsert_entity(tenant_id, ent)
            entities_count += 1
            if ent["entity_id"] not in seen_entity_ids:
                seen_entity_ids.add(ent["entity_id"])
                entities_to_embed.append(ent)

        for rel in relations:
            insert_relation(tenant_id, rel)
            relations_count += 1

    if entities_to_embed:
        names = [e["name"] or "" for e in entities_to_embed]
        embs = embed_texts(names)
        records = [
            {"entity_id": e["entity_id"], "embedding": embs[i]}
            for i, e in enumerate(entities_to_embed)
        ]
        insert_ec_embeddings(tenant_id, records)

    logger.info(
        "index_ec tenant_id=%s raw_page_id=%s entities=%d relations=%d evidence=%d",
        tenant_id, raw_page_id, entities_count, relations_count, evidence_count,
    )
    return {
        "entities_count": entities_count,
        "relations_count": relations_count,
        "evidence_count": evidence_count,
        "indexed_ec_count": len(entities_to_embed),
    }
