"""Add domain, page_type, crawl_policy_version columns. Run: python -m apps.api.migrations.add_domain_page_type_crawl_policy_version."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from sqlalchemy import text

from apps.api.db import engine


def run() -> None:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE raw_page ADD COLUMN IF NOT EXISTS crawl_policy_version VARCHAR(12)"))
        conn.execute(text("DROP INDEX IF EXISTS ix_raw_page_domain"))
        conn.execute(text("ALTER TABLE sections ADD COLUMN IF NOT EXISTS domain VARCHAR(255)"))
        conn.execute(text("ALTER TABLE sections ADD COLUMN IF NOT EXISTS page_type VARCHAR(64)"))
        conn.execute(text("ALTER TABLE sections ADD COLUMN IF NOT EXISTS crawl_policy_version VARCHAR(12)"))
    print("Migration complete: added domain, page_type, crawl_policy_version")


if __name__ == "__main__":
    run()
