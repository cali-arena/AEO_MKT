"""Check exclusion rules against sample URLs."""

import json
from pathlib import Path

# Add project root to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.services.crawl_rules import is_url_allowed


def main() -> None:
    samples_path = Path(__file__).parent / "excluded_samples.json"
    with open(samples_path) as f:
        urls = json.load(f)

    for url in urls:
        allowed, reason = is_url_allowed(url)
        status = "allowed" if allowed else "denied"
        print(f"{status}\t{url}\t{reason or '-'}")


if __name__ == "__main__":
    main()
