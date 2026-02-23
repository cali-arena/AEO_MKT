-- ec_versions: store ec_version_hash per tenant
-- Run: psql $DATABASE_URL -f apps/api/migrations/add_ec_versions.sql

CREATE TABLE IF NOT EXISTS ec_versions (
    tenant_id VARCHAR(255) PRIMARY KEY,
    version_hash VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);
