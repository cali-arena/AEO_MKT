"""
EC entity extraction from section text.
Returns list of EntityMention with canonical_name, entity_type, start_offset, end_offset, confidence.
Default: regex + heuristics. Optional spaCy if EC_USE_SPACY=1 and model available.
"""

import hashlib
import os
import re
from dataclasses import dataclass

# US state abbreviations for location patterns
STATE_ABBREVS = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
)


@dataclass
class EntityMention:
    """Extracted entity mention with span and confidence."""

    canonical_name: str
    entity_type: str
    start_offset: int
    end_offset: int
    confidence: float
    quote_span: str | None = None


def normalize_canonical_name(text: str) -> str:
    """Deterministic normalization: strip, collapse whitespace, unify casing for storage."""
    s = re.sub(r"\s+", " ", text.strip())
    return s


def make_entity_id(tenant_id: str, entity_type: str, canonical_name: str) -> str:
    """Stable entity_id from tenant, type, and canonical name. Uses SHA1 hash."""
    norm = normalize_canonical_name(canonical_name).lower()
    payload = f"{tenant_id}:{entity_type}:{norm}"
    h = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return "ent_" + h


_spacy_nlp = None


def _get_spacy():
    """Load spaCy NER if EC_USE_SPACY=1 and model available."""
    if os.getenv("EC_USE_SPACY", "").strip() != "1":
        return None
    global _spacy_nlp
    if _spacy_nlp is not None:
        return _spacy_nlp
    try:
        import spacy
        _spacy_nlp = spacy.load("en_core_web_sm")
        return _spacy_nlp
    except (ImportError, OSError):
        return None


def _extract_spacy(text: str) -> list[EntityMention]:
    """Extract using spaCy NER. Maps labels to entity_type, assigns confidence by label."""
    nlp = _get_spacy()
    if nlp is None:
        return []
    doc = nlp(text)
    out = []
    label_confidence = {"PERSON": 0.95, "ORG": 0.9, "GPE": 0.9, "LOC": 0.85, "FAC": 0.85, "PRODUCT": 0.8}
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC", "FAC", "ORG", "PERSON", "PRODUCT"):
            name = normalize_canonical_name(ent.text)
            if name:
                conf = label_confidence.get(ent.label_, 0.7)
                out.append(EntityMention(
                    canonical_name=name,
                    entity_type=ent.label_,
                    start_offset=ent.start_char,
                    end_offset=ent.end_char,
                    confidence=conf,
                    quote_span=ent.text,
                ))
    return out


# Regex patterns for fallback
_RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_RE_PHONE = re.compile(r"\+?[\d][\d\-\(\) ]{6,}\d")
_RE_CPF = re.compile(r"\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}\b")
_RE_CNPJ = re.compile(r"\b\d{2}[.\s]?\d{3}[.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2}\b")
_RE_CAPITALIZED_PHRASE = re.compile(r"\b([A-Z][a-zA-Z0-9\-\.&]+(?:\s+[A-Z][a-zA-Z0-9\-\.&]+){1,4})\b")
_RE_CITY_STATE = re.compile(
    r"([A-Z][a-zA-Z\-\.]*(?:\s+[A-Z][a-zA-Z\-\.]*){0,2}),\s*(" + "|".join(STATE_ABBREVS) + r")\b"
)
_RE_STATE_ONLY = re.compile(r"\b(" + "|".join(STATE_ABBREVS) + r")\b")


def _extract_regex(text: str) -> list[EntityMention]:
    """Extract using regex and heuristics. Deterministic."""
    out = []
    seen: set[tuple[int, str]] = set()

    def add(span: str, etype: str, start: int, end: int, conf: float) -> None:
        key = (start, etype)
        if key in seen:
            return
        seen.add(key)
        name = normalize_canonical_name(span)
        if name and len(name) >= 2:
            out.append(EntityMention(
                canonical_name=name,
                entity_type=etype,
                start_offset=start,
                end_offset=end,
                confidence=conf,
                quote_span=span,
            ))

    for m in _RE_EMAIL.finditer(text):
        add(m.group(0), "EMAIL", m.start(), m.end(), 0.99)

    for m in _RE_CNPJ.finditer(text):
        add(m.group(0), "CNPJ", m.start(), m.end(), 0.98)

    for m in _RE_CPF.finditer(text):
        add(m.group(0), "CPF", m.start(), m.end(), 0.98)

    for m in _RE_PHONE.finditer(text):
        add(m.group(0), "PHONE", m.start(), m.end(), 0.9)

    for m in _RE_CITY_STATE.finditer(text):
        add(m.group(0), "LOC", m.start(), m.end(), 0.85)

    for m in _RE_STATE_ONLY.finditer(text):
        add(m.group(1), "LOC", m.start(), m.end(), 0.7)

    for m in _RE_CAPITALIZED_PHRASE.finditer(text):
        span = m.group(1)
        if len(span) >= 3 and span not in ("The", "And", "Or", "But", "For", "Nor", "So", "Yet"):
            add(span, "ORG", m.start(), m.end(), 0.75)

    return sorted(out, key=lambda x: (x.start_offset, x.end_offset))


def extract_entities(section_text: str) -> list[EntityMention]:
    """
    Extract entities and mention spans from section text.
    Uses spaCy if EC_USE_SPACY=1 and model available; otherwise regex + heuristics.
    Returns list of EntityMention (canonical_name, entity_type, start_offset, end_offset, confidence).
    """
    if not section_text or not section_text.strip():
        return []
    mentions = _extract_spacy(section_text)
    if not mentions:
        mentions = _extract_regex(section_text)
    return mentions
