"""Crawl rules: classify URLs into allowed/quote_flow/info_static."""

from urllib.parse import parse_qs, urlparse

# Hosts where we allow ONLY informational/static pages, exclude quote flows
RESTRICTIVE_HOSTS = {"quote.unitedglobalvanline.com"}

# Path prefixes that indicate quote flow (excluded)
DENY_PATH_PREFIXES = [
    "/quote",
    "/get-quote",
    "/get-a-quote",
    "/estimate",
    "/booking",
    "/book",
    "/checkout",
    "/reserve",
    "/flow",
    "/wizard",
]

# Path substrings (e.g. step patterns)
DENY_PATH_SUBSTRINGS = [
    "step-1",
    "step-2",
    "step1",
    "step2",
    "/step/",
]

# Query keys that indicate quote flow (compared lowercase)
DENY_QUERY_KEYS = ["step", "session", "token", "lead", "leadid", "quote_id"]

# Query key prefixes (any key starting with these, lowercase)
DENY_QUERY_PREFIXES = ["utm_"]

# Legacy aliases for tests/backward compat
QUOTE_FLOW_PATH_PREFIXES = DENY_PATH_PREFIXES
QUOTE_FLOW_QUERY_KEYS = DENY_QUERY_KEYS

PAGE_TYPE_INFO_STATIC = "info_static"
PAGE_TYPE_QUOTE_FLOW = "quote_flow"
PAGE_TYPE_UNKNOWN = "unknown"


def _normalize_host(host: str) -> str:
    """Lowercase, strip optional port and www prefix for comparison."""
    if not host:
        return ""
    h = host.lower()
    if ":" in h:
        h = h.split(":")[0]
    if h.startswith("www."):
        h = h[4:]
    return h


def _is_quote_flow(path: str, query: str) -> tuple[bool, str]:
    """Check if path/query indicates quote flow. Returns (is_quote_flow, reason)."""
    path_lower = (path or "/").lower()
    # Deny on path prefix
    for prefix in DENY_PATH_PREFIXES:
        if path_lower.startswith(prefix.lower()):
            return True, f"path starts with quote-flow prefix {prefix!r}"
    # Deny on path substring
    for substr in DENY_PATH_SUBSTRINGS:
        if substr in path_lower:
            return True, f"path contains denied substring {substr!r}"
    # Deny on exact query keys (normalize to lowercase)
    qs = parse_qs(query, keep_blank_values=True)
    qkeys_lower = {k.lower() for k in qs.keys()}
    deny_keys_lower = {k.lower() for k in DENY_QUERY_KEYS}
    found = qkeys_lower & deny_keys_lower
    if found:
        return True, f"query contains quote-flow keys {sorted(found)!r}"
    # Deny on query key prefix (utm_*)
    for prefix in DENY_QUERY_PREFIXES:
        for qk in qkeys_lower:
            if qk.startswith(prefix.lower()):
                return True, f"query key prefix denied {prefix!r}"
    return False, ""


def classify_url(url: str) -> tuple[bool, str, str]:
    """
    Classify URL for crawl decision.
    Returns (allowed, page_type, reason).
    page_type: "info_static" | "quote_flow" | "unknown"
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, PAGE_TYPE_UNKNOWN, f"invalid url: {e!r}"

    host = _normalize_host(parsed.hostname or "")
    path = parsed.path or "/"
    query = parsed.query
    is_flow, flow_reason = _is_quote_flow(path, query)

    if host in RESTRICTIVE_HOSTS:
        if is_flow:
            return False, PAGE_TYPE_QUOTE_FLOW, flow_reason
        return True, PAGE_TYPE_INFO_STATIC, ""

    if is_flow:
        return False, PAGE_TYPE_QUOTE_FLOW, flow_reason

    return True, PAGE_TYPE_UNKNOWN, ""


def is_url_allowed(url: str) -> tuple[bool, str]:
    """Backward-compatible: returns (allowed, reason) from classify_url."""
    allowed, _, reason = classify_url(url)
    return allowed, reason


def extract_domain(url: str) -> str:
    """Extract host (domain) from URL for storage."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return _normalize_host(host) or ""
    except Exception:
        return ""
