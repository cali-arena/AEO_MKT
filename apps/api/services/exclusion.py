"""URL-based exclusion classification. No crawling."""

import re
from urllib.parse import parse_qs, urlparse

PAGE_TYPE_EXCLUDED = "ui_flow_excluded"
PAGE_TYPE_ALLOWED = "info_static"

DENY_PATH_PREFIXES = [
    "/quote",
    "/get-quote",
    "/get-a-quote",
    "/estimate",
    "/booking",
    "/flow",
    "/wizard",
]

DENY_PATH_SUBSTRINGS = [
    "step-1",
    "step-2",
    "step1",
    "step2",
    "/step/",
]

DENY_QUERY_KEYS = ["step", "session", "token", "leadid"]

DENY_QUERY_PREFIXES = ["utm_"]

FORM_TAG_PATTERNS = [
    r"<form\b",
    r"<input\b",
    r"<select\b",
    r"<textarea\b",
    r"<button\b",
    r"aria-label\s*=",
]


def ui_flow_heuristic(html: str, text: str) -> tuple[bool, str, dict]:
    """
    Form-UI heuristic: short text + form-heavy HTML -> likely UI flow page.
    Returns (excluded, reason, details).
    reason format: "ui_form_heuristic:text_len=...,tag_hits=...,density=..."
    details: {"text_len": int, "tag_hits": int, "density": float} for logging.
    """
    text_len = len(text.strip())
    html_lower = html.lower()

    tag_hits = 0
    for pat in FORM_TAG_PATTERNS:
        tag_hits += len(re.findall(pat, html_lower))

    form_density = tag_hits / max(1, text_len)
    density_str = f"{form_density:.4f}".rstrip("0").rstrip(".")

    excluded = False
    if text_len < 600 and tag_hits >= 12:
        excluded = True
    elif form_density > 0.03 and text_len < 1200:
        excluded = True

    reason = f"ui_form_heuristic:text_len={text_len},tag_hits={tag_hits},density={density_str}"
    details = {"text_len": text_len, "tag_hits": tag_hits, "density": form_density}
    return (excluded, reason, details)


def should_exclude(
    url: str,
    html: str | None = None,
    text: str | None = None,
) -> tuple[bool, str, str, dict | None]:
    """
    Returns (excluded, reason, page_type, heuristic_info).
    page_type is "ui_flow_excluded" when excluded, else "info_static".
    heuristic_info is None unless form-UI heuristic ran; then {"text_len", "tag_hits", "density"}.
    If html and text are provided, runs form-UI heuristic after URL rules pass.
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        return True, f"invalid_url:{e!r}", PAGE_TYPE_EXCLUDED, None

    path = (parsed.path or "/").lower()
    query = (parsed.query or "").lower()

    # Deny path prefix
    for prefix in DENY_PATH_PREFIXES:
        if path.startswith(prefix.lower()):
            return True, f"deny_path_prefix:{prefix}", PAGE_TYPE_EXCLUDED, None

    # Deny path contains
    for substr in DENY_PATH_SUBSTRINGS:
        if substr in path:
            return True, f"deny_path_contains:{substr}", PAGE_TYPE_EXCLUDED, None

    # Deny query keys (lowercase)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qkeys_lower = {k.lower() for k in qs.keys()}
    deny_keys_lower = {k.lower() for k in DENY_QUERY_KEYS}
    found = qkeys_lower & deny_keys_lower
    if found:
        key = sorted(found)[0]
        return True, f"deny_query_key:{key}", PAGE_TYPE_EXCLUDED, None

    # Deny query key prefix (utm_)
    for qk in qkeys_lower:
        for prefix in DENY_QUERY_PREFIXES:
            if qk.startswith(prefix.lower()):
                return True, f"deny_query_prefix:{qk}", PAGE_TYPE_EXCLUDED, None

    # Form-UI heuristic when html and text provided
    if html is not None and text is not None:
        excluded, reason, details = ui_flow_heuristic(html, text)
        if excluded:
            return True, reason, PAGE_TYPE_EXCLUDED, details
        return False, "", PAGE_TYPE_ALLOWED, details

    return False, "", PAGE_TYPE_ALLOWED, None
