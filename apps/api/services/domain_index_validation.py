"""Per-domain index validation: counts with strict tenant_id + domain filters.

All counts use WHERE tenant_id=:tenant_id AND domain=:domain (no global counts).
"""

from apps.api.services.repo import (
    count_ac_embeddings_by_domain,
    count_ec_embeddings_by_domain,
    count_raw_pages_by_domain,
    count_sections_by_domain,
)


def count_raw_pages(tenant_id: str, domain: str) -> int:
    """Count raw_pages for (tenant_id, domain). Strict filters."""
    return count_raw_pages_by_domain(tenant_id, domain)


def count_sections(tenant_id: str, domain: str) -> int:
    """Count sections for (tenant_id, domain). Strict filters."""
    return count_sections_by_domain(tenant_id, domain)


def count_ac_embeddings(tenant_id: str, domain: str) -> int:
    """Count ac_embeddings for (tenant_id, domain). Strict filters."""
    return count_ac_embeddings_by_domain(tenant_id, domain)


def count_ec_embeddings(tenant_id: str, domain: str) -> int:
    """Count ec_embeddings for (tenant_id, domain). Strict filters."""
    return count_ec_embeddings_by_domain(tenant_id, domain)


def get_domain_index_stats(tenant_id: str, domain: str) -> dict:
    """
    Return per-domain index stats and index_state for debugging.
    Keys: raw_pages, sections, ac_embeddings, ec_embeddings, index_state.
    """
    from apps.api.services.repo import get_domain_index_state

    return {
        "raw_pages": count_raw_pages(tenant_id, domain),
        "sections": count_sections(tenant_id, domain),
        "ac_embeddings": count_ac_embeddings(tenant_id, domain),
        "ec_embeddings": count_ec_embeddings(tenant_id, domain),
        "index_state": get_domain_index_state(tenant_id, domain) or {},
    }
