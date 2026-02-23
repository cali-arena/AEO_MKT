"""Policy loader and crawl policy version."""

import hashlib
import json
from pathlib import Path
from typing import Any

# Default path relative to project root
DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent.parent.parent / "policy" / "policy.json"


def canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization: compact, sorted keys."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    """Load policy from JSON file."""
    p = Path(path) if path is not None else DEFAULT_POLICY_PATH
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def crawl_policy_version(policy: dict[str, Any]) -> str:
    """SHA256 of canonical JSON, first 12 hex chars."""
    payload = canonical_json(policy)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def main() -> None:
    policy = load_policy()
    version = crawl_policy_version(policy)
    print(version)


if __name__ == "__main__":
    main()
