"""Add EC storage schema: entities (canonical_name, metadata, timestamps), entity_mentions, ec_embeddings (model, dim, created_at).

Run: python -m apps.api.migrations.add_ec_storage_schema
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from sqlalchemy import text

from apps.api.db import engine


def run() -> None:
    with engine.begin() as conn:
        # entities: add canonical_name, metadata jsonb, created_at, updated_at
        conn.execute(text("ALTER TABLE entities ADD COLUMN IF NOT EXISTS canonical_name VARCHAR(512)"))
        conn.execute(text("ALTER TABLE entities ADD COLUMN IF NOT EXISTS metadata JSONB"))
        conn.execute(text("ALTER TABLE entities ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ"))
        conn.execute(text("ALTER TABLE entities ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ"))

        # entity_mentions: create table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS entity_mentions (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(255) NOT NULL,
                mention_id UUID NOT NULL DEFAULT gen_random_uuid(),
                entity_id VARCHAR(255) NOT NULL,
                section_id VARCHAR(255) NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                quote_span TEXT,
                confidence FLOAT,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_entity_mentions_tenant_id ON entity_mentions (tenant_id, mention_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_entity_mentions_tenant_entity ON entity_mentions (tenant_id, entity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_entity_mentions_tenant_section ON entity_mentions (tenant_id, section_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_entity_mentions_tenant ON entity_mentions (tenant_id)"))

        # ec_embeddings: add model, dim, created_at
        conn.execute(text("ALTER TABLE ec_embeddings ADD COLUMN IF NOT EXISTS model VARCHAR(128)"))
        conn.execute(text("ALTER TABLE ec_embeddings ADD COLUMN IF NOT EXISTS dim INTEGER"))
        conn.execute(text("ALTER TABLE ec_embeddings ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()"))

    print("Migration complete: EC storage schema (entities, entity_mentions, ec_embeddings)")


if __name__ == "__main__":
    run()
