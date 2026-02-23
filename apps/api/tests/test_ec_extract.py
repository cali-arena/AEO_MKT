"""Unit tests for ec_extract: normalization, hashing, offsets."""

import pytest

from apps.api.services.ec_extract import (
    EntityMention,
    extract_entities,
    make_entity_id,
    normalize_canonical_name,
)


def test_normalize_canonical_name_strip_and_collapse() -> None:
    assert normalize_canonical_name("  Foo  Bar  ") == "Foo Bar"
    assert normalize_canonical_name("\n\tx  y\n") == "x y"


def test_normalize_canonical_name_deterministic() -> None:
    assert normalize_canonical_name("A B C") == normalize_canonical_name("A  B   C")
    assert normalize_canonical_name("X") == "X"


def test_make_entity_id_stable_hash() -> None:
    a = make_entity_id("t1", "ORG", "Acme Corp")
    b = make_entity_id("t1", "ORG", "Acme Corp")
    assert a == b
    assert a.startswith("ent_")
    assert len(a) == 20


def test_make_entity_id_different_inputs_different_ids() -> None:
    id1 = make_entity_id("t1", "ORG", "Acme")
    id2 = make_entity_id("t2", "ORG", "Acme")
    id3 = make_entity_id("t1", "PERSON", "Acme")
    id4 = make_entity_id("t1", "ORG", "Acme Corp")
    assert id1 != id2 != id3 != id4


def test_make_entity_id_normalizes_canonical_name() -> None:
    id_a = make_entity_id("t1", "ORG", "Acme  Corp")
    id_b = make_entity_id("t1", "ORG", "Acme Corp")
    assert id_a == id_b


def test_extract_entities_offsets_match_quote_span() -> None:
    text = "Contact us at sales@example.com or call +1-555-123-4567."
    mentions = extract_entities(text)
    for m in mentions:
        assert m.quote_span is not None
        extracted = text[m.start_offset:m.end_offset]
        assert extracted == m.quote_span, f"offset mismatch: {extracted!r} vs {m.quote_span!r}"


def test_extract_entities_email_and_phone() -> None:
    text = "Email: john@test.com  Phone: (555) 123-4567"
    mentions = extract_entities(text)
    types = {m.entity_type for m in mentions}
    assert "EMAIL" in types
    assert "PHONE" in types
    assert any("john@test.com" in (m.quote_span or "") for m in mentions)
    assert any("555" in (m.quote_span or "") for m in mentions)


def test_extract_entities_cpf_cnpj() -> None:
    text = "CPF: 123.456.789-00  CNPJ: 12.345.678/0001-90"
    mentions = extract_entities(text)
    types = {m.entity_type for m in mentions}
    assert "CPF" in types
    assert "CNPJ" in types


def test_extract_entities_empty_returns_empty() -> None:
    assert extract_entities("") == []
    assert extract_entities("   \n\t  ") == []


def test_extract_entities_confidence_in_range() -> None:
    text = "Email: a@b.com in Dallas, TX"
    mentions = extract_entities(text)
    for m in mentions:
        assert 0.0 <= m.confidence <= 1.0


def test_extract_entities_canonical_name_normalized() -> None:
    text = "Contact  Acme   Corp"
    mentions = extract_entities(text)
    for m in mentions:
        assert m.canonical_name == normalize_canonical_name(m.canonical_name)
        assert "  " not in m.canonical_name
