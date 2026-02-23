"""Deterministic normalization for hashing and stable section IDs only."""

import hashlib
import re


def normalize_for_id(text: str) -> str:
    """
    Normalize text for hashing and stable IDs.
    - strip
    - collapse whitespace runs (spaces/tabs) to single spaces
    - normalize newlines (\\r\\n, \\r -> \\n)
    - remove trailing spaces per line (strip each line)
    """
    s = text.strip()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    lines = [line.strip() for line in s.split("\n")]
    return "\n".join(lines)


def sha256_hex(s: str) -> str:
    """Return SHA256 hex digest of string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
