"""Metadata helpers for URLs and pages."""

from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """Extract hostname from URL, normalized (lowercase, no www, no port)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if not host:
            return ""
        h = host.lower()
        if ":" in h:
            h = h.split(":")[0]
        if h.startswith("www."):
            h = h[4:]
        return h
    except Exception:
        return ""
