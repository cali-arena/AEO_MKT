-- EC storage schema: entities (canonical_name, metadata, timestamps), entity_mentions, ec_embeddings (model, dim, created_at)
-- Run: psql $DATABASE_URL -f apps/api/migrations/add_ec_storage_schema.sql

-- entities: add canonical_name, metadata jsonb, timestamps
ALTER TABLE entities ADD COLUMN IF NOT EXISTS canonical_name VARCHAR(512);
ALTER TABLE entities ADD COLUMN IF NOT EXISTS metadata JSONB;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- entity_mentions: new table
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
);

CREATE INDEX IF NOT EXISTS ix_entity_mentions_tenant_id ON entity_mentions (tenant_id, mention_id);
CREATE INDEX IF NOT EXISTS ix_entity_mentions_tenant_entity ON entity_mentions (tenant_id, entity_id);
CREATE INDEX IF NOT EXISTS ix_entity_mentions_tenant_section ON entity_mentions (tenant_id, section_id);
CREATE INDEX IF NOT EXISTS ix_entity_mentions_tenant ON entity_mentions (tenant_id);

-- ec_embeddings: add model, dim, created_at
ALTER TABLE ec_embeddings ADD COLUMN IF NOT EXISTS model VARCHAR(128);
ALTER TABLE ec_embeddings ADD COLUMN IF NOT EXISTS dim INTEGER;
ALTER TABLE ec_embeddings ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
