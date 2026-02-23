"""Page type inference from URL, title, and text."""

import re
from urllib.parse import urlparse

PAGE_TYPE_FAQ = "faq"
PAGE_TYPE_SERVICE = "service"
PAGE_TYPE_BLOG = "blog"
PAGE_TYPE_INFORMATIONAL = "informational"
PAGE_TYPE_UNKNOWN = "unknown"

INFORMATIONAL_KEYWORDS = ["about", "company", "mission", "locations"]


def infer_page_type(url: str, title: str | None = None, text: str | None = None) -> str:
    """
    Infer page type from URL, title, and text.
    Returns: faq | service | blog | informational | unknown
    """
    path = (urlparse(url).path or "/").lower()
    title_lower = (title or "").lower()
    text_lower = (text or "").lower()

    # faq
    if "/faq" in path or "faq" in title_lower:
        return PAGE_TYPE_FAQ

    # service
    if "/services" in path or "service" in title_lower:
        return PAGE_TYPE_SERVICE

    # blog: path, title, or dated article pattern (e.g. /2024/01/, /blog/2024-01-)
    if "/blog" in path or "blog" in title_lower:
        return PAGE_TYPE_BLOG
    if re.search(r"/\d{4}(/|-)", path):
        return PAGE_TYPE_BLOG

    # informational: text length > 800 and contains keywords
    if text and len(text.strip()) > 800:
        for kw in INFORMATIONAL_KEYWORDS:
            if kw in text_lower:
                return PAGE_TYPE_INFORMATIONAL

    return PAGE_TYPE_UNKNOWN
