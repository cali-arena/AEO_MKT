"""Shared domain gate: hostname normalization and effective allowed domains for ingest/crawl.

Effective allowlist = static policy.allowed_domains UNION tenant registered domains (from DB)
UNION current requested domain (so the domain being evaluated in this run is always allowed).
"""

from apps.api.services.policy import load_policy
from apps.api.services.repo import list_eval_domains


def normalize_host(host: str | None) -> str:
    """Single shared hostname normalizer: strip, lowercase. Use with parsed host from URL."""
    if host is None:
        return ""
    return (host or "").strip().lower()


def get_effective_allowed_domains(
    tenant_id: str | None,
    requested_domain: str | None = None,
) -> set[str]:
    """
    Build effective allowlist for domain gate:
    policy.allowed_domains UNION tenant registered eval domains UNION requested_domain (current crawl target).

    - tenant_id: when set, include list_eval_domains(tenant_id).
    - requested_domain: when set, always include so the domain being evaluated this run is allowed.
    Returns set of normalized hostnames (exact match only; no off-domain).
    """
    policy = load_policy()
    policy_allowed = [
        normalize_host(d) for d in policy.get("allowed_domains", []) if d
    ]
    registered = (
        [normalize_host(d) for d in list_eval_domains(tenant_id) if d]
        if tenant_id
        else []
    )
    effective = set(policy_allowed) | set(registered)
    # Only allow current requested domain when we have tenant context (ingest/evaluate run)
    if requested_domain and tenant_id:
        effective.add(normalize_host(requested_domain))
    return effective
