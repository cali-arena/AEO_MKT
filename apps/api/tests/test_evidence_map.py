"""Unit tests for evidence_map builder."""

import pytest

from apps.api.services.evidence_map import (
    build_evidence_map,
    evidence_records_for_insert,
)


def test_build_evidence_map_returns_expected_shape() -> None:
    """evidence_map: evidence_id -> {tenant_id, url, section_id, quote_span}."""
    results = [
        {"section_id": "sec_1", "url": "https://a.com", "quote_span": "Quote one"},
    ]
    m = build_evidence_map("tenant_x", results)
    assert len(m) == 1
    eid = next(iter(m))
    ev = m[eid]
    assert set(ev) == {"tenant_id", "url", "section_id", "quote_span"}
    assert ev["tenant_id"] == "tenant_x"
    assert ev["url"] == "https://a.com"
    assert ev["section_id"] == "sec_1"
    assert ev["quote_span"] == "Quote one"


def test_evidence_id_deterministic() -> None:
    """Same inputs produce same evidence_id."""
    results = [{"section_id": "s1", "url": "https://x.com", "quote_span": "text"}]
    m1 = build_evidence_map("t1", results)
    m2 = build_evidence_map("t1", results)
    assert set(m1.keys()) == set(m2.keys())
    assert list(m1.keys())[0] == list(m2.keys())[0]


def test_evidence_id_different_for_different_content() -> None:
    """Different section/url/quote produce different evidence_id."""
    r1 = [{"section_id": "s1", "url": "https://a.com", "quote_span": "A"}]
    r2 = [{"section_id": "s2", "url": "https://b.com", "quote_span": "B"}]
    m1 = build_evidence_map("t", r1)
    m2 = build_evidence_map("t", r2)
    assert list(m1.keys())[0] != list(m2.keys())[0]


def test_evidence_id_includes_tenant() -> None:
    """Different tenant_id produces different evidence_id for same section/url/quote."""
    results = [{"section_id": "s1", "url": "https://x.com", "quote_span": "x"}]
    m1 = build_evidence_map("tenant_a", results)
    m2 = build_evidence_map("tenant_b", results)
    assert list(m1.keys())[0] != list(m2.keys())[0]


def test_evidence_records_for_insert_includes_evidence_id() -> None:
    """Records have evidence_id and match build_evidence_map keys."""
    results = [
        {
            "section_id": "sec_1",
            "url": "https://a.com",
            "quote_span": "Q1",
            "start_char": 0,
            "end_char": 2,
            "version_hash": "v1",
        },
    ]
    m = build_evidence_map("t", results)
    records = evidence_records_for_insert("t", results)
    assert len(records) == 1
    assert records[0]["evidence_id"] in m
    assert records[0]["section_id"] == "sec_1"
    assert records[0]["quote_span"] == "Q1"
    assert records[0]["start_char"] == 0
    assert records[0]["version_hash"] == "v1"


def test_deduplicates_identical_evidence() -> None:
    """Same section_id+url+quote_span deduplicated."""
    results = [
        {"section_id": "s1", "url": "https://x.com", "quote_span": "same"},
        {"section_id": "s1", "url": "https://x.com", "quote_span": "same"},
    ]
    m = build_evidence_map("t", results)
    records = evidence_records_for_insert("t", results)
    assert len(m) == 1
    assert len(records) == 1
