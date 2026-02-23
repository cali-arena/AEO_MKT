"""Deterministic text normalization and content hashing."""

import hashlib
import re


def normalize_text(text: str) -> str:
    """
    Normalize text for deterministic hashing.
    - strip
    - replace \\r\\n with \\n
    - collapse multiple newlines to max 2
    - collapse whitespace runs (spaces/tabs) to single spaces
    - strip each line
    """
    s = text.strip()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    lines = [line.strip() for line in s.split("\n")]
    return "\n".join(lines)


def content_hash(text: str) -> str:
    """Return SHA256 hex digest of normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
