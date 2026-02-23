#!/usr/bin/env python
"""
Build Entity Corpus (EC) for a tenant from sections.

Usage:
  python -m scripts.build_ec <tenant_id>

  Or from project root:
  python scripts/build_ec.py <tenant_id>

Requires DATABASE_URL. Uses embedding provider (DeterministicEmbeddingProvider when ENV=test).
"""

import argparse
import logging
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from apps.api.db import ensure_tables
from apps.api.services.index_ec import build_ec

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Entity Corpus from sections for a tenant")
    parser.add_argument("tenant_id", help="Tenant ID to build EC for")
    parser.add_argument("--ensure-tables", action="store_true", help="Run ensure_tables() before build")
    args = parser.parse_args()

    if not args.tenant_id or not args.tenant_id.strip():
        logger.error("tenant_id is required")
        sys.exit(1)

    if args.ensure_tables:
        ensure_tables()

    result = build_ec(args.tenant_id)
    logger.info(
        "build_ec done: entities=%d mentions=%d indexed_ec=%d ec_version_hash=%s",
        result["entities_count"],
        result["mentions_count"],
        result["indexed_ec_count"],
        result["ec_version_hash"],
    )
    print(
        f"EC built: {result['entities_count']} entities, "
        f"{result['mentions_count']} mentions, "
        f"ec_version_hash={result['ec_version_hash']}"
    )


if __name__ == "__main__":
    main()
