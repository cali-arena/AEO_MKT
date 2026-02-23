-- Add domain, page_type, crawl_policy_version to raw_page and section.
-- Run with: psql $DATABASE_URL -f apps/api/migrations/add_domain_page_type_crawl_policy_version.sql

-- raw_page: add crawl_policy_version (domain, page_type may already exist)
ALTER TABLE raw_page ADD COLUMN IF NOT EXISTS crawl_policy_version VARCHAR(12);

-- raw_page: drop index on domain if present (per request: index=False)
DROP INDEX IF EXISTS ix_raw_page_domain;

-- sections: add domain, page_type, crawl_policy_version
ALTER TABLE sections ADD COLUMN IF NOT EXISTS domain VARCHAR(255);
ALTER TABLE sections ADD COLUMN IF NOT EXISTS page_type VARCHAR(64);
ALTER TABLE sections ADD COLUMN IF NOT EXISTS crawl_policy_version VARCHAR(12);
