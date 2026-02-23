-- Add domain, page_type, crawl_policy_version to raw_page and sections.
-- Run with: psql $DATABASE_URL -f infra/migrations/002_add_domain_page_type_policy_version.sql

ALTER TABLE raw_page ADD COLUMN domain VARCHAR(255);
ALTER TABLE raw_page ADD COLUMN page_type VARCHAR(64);
ALTER TABLE raw_page ADD COLUMN crawl_policy_version VARCHAR(12);

ALTER TABLE sections ADD COLUMN domain VARCHAR(255);
ALTER TABLE sections ADD COLUMN page_type VARCHAR(64);
ALTER TABLE sections ADD COLUMN crawl_policy_version VARCHAR(12);

-- Composite indexes for tenant + domain and tenant + crawl_policy_version
CREATE INDEX ix_raw_page_tenant_domain ON raw_page (tenant_id, domain);
CREATE INDEX ix_raw_page_tenant_policy ON raw_page (tenant_id, crawl_policy_version);

CREATE INDEX ix_sections_tenant_domain ON sections (tenant_id, domain);
CREATE INDEX ix_sections_tenant_policy ON sections (tenant_id, crawl_policy_version);
