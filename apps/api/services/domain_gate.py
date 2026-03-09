"""Shared domain gate: hostname normalization and effective allowed domains for ingest/crawl.

Effective allowlist = static policy.allowed_domains UNION tenant registered domains (from DB)
UNION current requested domain (so the domain being evaluated in this run is always allowed).
"""

from apps.api.services.policy import load_policy
from apps.api.services.repo import list_eval_domains


def normalize_host(host: str | None) -> str:
    """Shared hostname normalizer: strip, lowercase, no trailing dot. Host only (no scheme/path)."""
    if host is None:
        return ""
    return (host or "").strip().lower().strip(".")


def get_effective_allowed_domains(
    tenant_id: str | None,
    requested_domain: str | None = None,
) -> tuple[set[str], list[str], list[str]]:
    """
    Build effective allowlist: static policy U tenant registered U requested_domain (when tenant_id set).
    Returns (effective_set, static_allowed_list, tenant_registered_list) for logging.
    """
    policy = load_policy()
    static_allowed = [normalize_host(d) for d in policy.get("allowed_domains", []) if d]
    tenant_registered = (
        [normalize_host(d) for d in list_eval_domains(tenant_id) if d]
        if tenant_id
        else []
    )
    effective = set(static_allowed) | set(tenant_registered)
    if requested_domain and tenant_id:
        effective.add(normalize_host(requested_domain))
    return (effective, static_allowed, tenant_registered)
