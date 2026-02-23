# Database Schema (Milestone 1)

## Tables

### raw_page

Crawled HTML pages. One row per URL per tenant after ingest.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT PK | Auto-increment |
| tenant_id | VARCHAR(255) NOT NULL, indexed | Tenant scope |
| url | TEXT NOT NULL, indexed | Original request URL |
| canonical_url | TEXT | Final URL after redirects |
| html | TEXT | Raw HTML |
| text | TEXT | Extracted visible text |
| status_code | INT | HTTP status |
| fetched_at | TIMESTAMPTZ | Fetch timestamp |
| content_hash | VARCHAR(64), indexed | Hash of text for deduplication |
| version | INT NOT NULL | Increments on content change |
| domain | VARCHAR(255), indexed | Host from canonical_url |
| page_type | VARCHAR(64) | "info_static" \| "quote_flow" \| "unknown" |
| crawl_decision | VARCHAR(32) | "allowed" \| "excluded" |
| crawl_reason | VARCHAR(512) | Reason when excluded |

**Constraints:** `id` primary key.

---

### sections

Text chunks from raw_page. Overlapping chunks (~1050 chars, 150 overlap).

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT PK | Auto-increment |
| tenant_id | VARCHAR(255) NOT NULL, indexed | Tenant scope |
| raw_page_id | BIGINT NOT NULL, FK→raw_page.id CASCADE | Parent page |
| section_id | VARCHAR(255) NOT NULL, indexed | Stable ID: sec_+sha1(url:chunk_index)[:16] |
| heading_path | TEXT | Optional heading hierarchy |
| text | TEXT | Chunk content |
| start_char | INT | Start offset in full raw_page.text |
| end_char | INT | End offset in full raw_page.text |
| section_hash | VARCHAR(64), indexed | Hash of chunk text |
| version_hash | VARCHAR(64), indexed | Hash of chunk text (content version) |
| created_at | TIMESTAMPTZ | Insert time |

**Constraints:** `id` primary key, `raw_page_id` foreign key with ON DELETE CASCADE.

---

### evidence

Grounding spans: exact quote positions for answers. Created on-demand in /answer.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT PK | Auto-increment |
| tenant_id | VARCHAR(255) NOT NULL, indexed | Tenant scope |
| evidence_id | VARCHAR(255) NOT NULL, indexed | Stable evidence ID |
| section_id | VARCHAR(255) NOT NULL, indexed | Section this span belongs to |
| url | TEXT | Page URL |
| quote_span | TEXT | Extracted quote text |
| start_char | INT | Start offset in **section.text** |
| end_char | INT | End offset in **section.text** |
| version_hash | VARCHAR(64), indexed | Matches section.version_hash |
| created_at | TIMESTAMPTZ | Insert time |

**Constraints:** `id` primary key.

**Evidence offsets:** `start_char` and `end_char` are relative to `sections.text`, not raw_page.text. Invariant: `quote_span == section.text[start_char:end_char]`.

---

### ac_embeddings

Vector embeddings for Assistant Context (AC) retrieval. One per section.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT PK | Auto-increment |
| tenant_id | VARCHAR(255) NOT NULL, indexed | Tenant scope |
| section_id | VARCHAR(255) NOT NULL, indexed | Section reference |
| embedding | vector(384) NOT NULL | bge-small-en-v1.5 embedding |

**Constraints:** `id` primary key.

---

### entities

Named entities extracted by index_ec from sections. One per entity mention per section.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT PK | Auto-increment |
| tenant_id | VARCHAR(255) NOT NULL, indexed | Tenant scope |
| entity_id | VARCHAR(255) NOT NULL, indexed | Stable entity ID |
| name | VARCHAR(512) | Entity name (e.g. "Coast to Coast Movers") |
| type | VARCHAR(128) | Entity type (e.g. ORG, PERSON) |
| section_id | VARCHAR(255), indexed | Source section |
| evidence_id | VARCHAR(255), indexed | Related evidence row |

**Constraints:** `id` primary key, **unique (tenant_id, entity_id)**.

**Indexes:** (tenant_id, name), (tenant_id, section_id).

---

### relations

Subject–predicate–object triples between entities. Extracted by index_ec.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT PK | Auto-increment |
| tenant_id | VARCHAR(255) NOT NULL, indexed | Tenant scope |
| subject_entity_id | VARCHAR(255) NOT NULL, indexed | Subject entity |
| predicate | VARCHAR(256) | Relation type |
| object_entity_id | VARCHAR(255) NOT NULL, indexed | Object entity |
| evidence_id | VARCHAR(255), indexed | Related evidence row |

**Constraints:** `id` primary key.

**Indexes:** (tenant_id, subject_entity_id).

---

### ec_embeddings

Vector embeddings for Entity Context (EC) retrieval. One per entity.

| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT PK | Auto-increment |
| tenant_id | VARCHAR(255) NOT NULL, indexed | Tenant scope |
| entity_id | VARCHAR(255) NOT NULL, indexed | Entity reference |
| embedding | vector(384) NOT NULL | bge-small-en-v1.5 on entity name |

**Constraints:** `id` primary key.

**Indexes:** (tenant_id, entity_id).

---

## Tenant ID enforcement

**Rule:** All repository queries MUST include `tenant_id` in the WHERE clause.

- Repo layer enforces this; `_assert_tenant(tenant_id)` raises if tenant_id is None or empty.
- Repo is the only place allowed to run DB reads/writes.
- Multi-tenancy is enforced at the data layer; APIs pass tenant_id from auth (Bearer token or X-Tenant-Debug).

---

## version_hash behavior

- **Sections:** `version_hash` = SHA256 of chunk text. Same `section_id` (stable by URL + chunk index) gets a new `version_hash` when chunk content changes.
- **Evidence:** `version_hash` matches the section’s at creation time; used for consistency checks.
- **Stability:** `section_id` is stable across content changes; `version_hash` changes when content changes.
- **Usage:** Caching, retrieval, and grounding use `version_hash` to detect stale content.
