"""URL normalization utilities."""

from urllib.parse import urlparse, urlunparse

DEFAULT_PORTS = {"http": 80, "https": 443}


def canonicalize_url(url: str) -> tuple[str, str]:
    """
    Returns (canonical_url, domain).

    Rules:
    - lowercase hostname
    - strip fragment
    - normalize trailing slash (remove unless root path)
    - remove default ports (80 for http, 443 for https)
    """
    parsed = urlparse(url)

    # Lowercase hostname
    host = (parsed.hostname or "").lower()
    if not host:
        return (url, "")

    # Strip fragment
    fragment = ""

    # Remove default port
    port = parsed.port
    if port is not None and port == DEFAULT_PORTS.get(parsed.scheme or "http"):
        port = None

    # Build netloc (host:port, omit port if default)
    netloc = host
    if port is not None and port not in (80, 443):
        netloc = f"{host}:{port}"

    # Normalize trailing slash: remove unless path is "/" (root)
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    canonical = urlunparse((
        parsed.scheme or "https",
        netloc,
        path,
        parsed.params,
        parsed.query,
        fragment,
    ))

    return (canonical, host)
