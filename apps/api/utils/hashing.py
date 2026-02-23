"""Stable hash functions for section_hash and version_hash."""

import hashlib


def section_hash(text: str) -> str:
    """Stable hash of section text. Same text always yields same hash."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def version_hash(text: str, extra: str = "") -> str:
    """Stable hash of section text plus optional extra. Changed text yields different hash."""
    payload = text + extra
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
