# Troubleshooting: ac_embeddings / ec_embeddings always 0

Use this when `SELECT COUNT(*) FROM ac_embeddings` (and ec_embeddings) stay 0 even after pgvector is working.

## How embeddings get populated

1. **Trigger:** Someone calls **evaluate** for a domain (or an orchestration job does). That calls `ensure_ingested(tenant_id, domain)`.
2. **Enqueue:** `ensure_ingested` inserts a row into **domain_ingest_job** (status PENDING).
3. **Worker:** The worker loop claims one **domain_ingest_job**, then runs **ingest_domain_sync(tenant_id, domain)**.
4. **Ingest:** For each URL `https://{domain}` and `http://{domain}` the pipeline: **fetch** → **ingest** (raw_page) → **sectionize** → **index_ac** (writes ac_embeddings) → then **index_ec** (writes ec_embeddings).

If any step fails or never runs, counts stay 0.

---

## 1. Run these on the server (DB checks)

From project root, same `.env` you use for compose.

### Recent ingest jobs (status and errors)

```bash
docker exec infra-db-1 psql -U postgres -d ai_mkt -c "
SELECT id, tenant_id, domain, status, error_code, LEFT(error_message, 80) AS err, created_at, finished_at
FROM domain_ingest_job
ORDER BY created_at DESC
LIMIT 10;
"
```

- If there are **no rows** → no one has triggered ingest (e.g. evaluate never called for any domain).
- If status is **FAILED** → check `error_code` and `error_message` (and worker logs).

### Domain index state (per-domain status)

```bash
docker exec infra-db-1 psql -U postgres -d ai_mkt -c "
SELECT tenant_id, domain, status, error_code, LEFT(last_error, 80) AS err
FROM domain_index_state
ORDER BY updated_at DESC
LIMIT 10;
"
```

### Do you have raw_pages and sections?

```bash
docker exec infra-db-1 psql -U postgres -d ai_mkt -c "
SELECT
  (SELECT COUNT(*) FROM raw_page) AS raw_pages,
  (SELECT COUNT(*) FROM sections) AS sections,
  (SELECT COUNT(*) FROM ac_embeddings) AS ac_embeddings,
  (SELECT COUNT(*) FROM ec_embeddings) AS ec_embeddings;
"
```

- **raw_pages = 0** → fetch/ingest never ran or domain was excluded/not allowed.
- **sections > 0 but ac_embeddings = 0** → pipeline ran up to sectionize but **index_ac** failed (e.g. embedding API error, or earlier pgvector error if you had the wrong image).

---

## 2. Worker logs (where errors show up)

```bash
docker compose -f infra/docker-compose.yml --env-file .env logs -f --tail=200 worker
```

Look for:

- `ingest_job_start` / `ingest_job_done` / `ingest_job_failed`
- `ingest_attempt_failed` (per-URL failure inside ingest_domain_sync)
- `ingest_job_empty_index` (sections or ac_embeddings still 0 after run)
- `domain_not_allowed` (domain not in policy)
- Any Python tracebacks (embedding API, DB, etc.)

---

## 3. Policy: is your domain allowed?

Ingest only runs for domains in **allowed_domains** in `policy/policy.json`. The pipeline raises `ValueError("domain_not_allowed")` otherwise.

- Check on server: `cat policy/policy.json` (or the path your API uses).
- Default in this repo: `allowed_domains` includes e.g. `coasttocoastmovers.com`, `quote.unitedglobalvanline.com`; `tenant_id` is `coast2coast`.
- If you evaluate a domain **not** in that list, ingest will fail with domain_not_allowed and no embeddings will be written.

---

## 4. Trigger ingest and re-check

1. Call **evaluate** for a domain that is in **allowed_domains** and that the worker can fetch (e.g. `coasttocoastmovers.com` for the default policy).
2. Wait for the worker to pick up the ingest job (watch worker logs for `ingest_job_start` / `ingest_job_done` or `ingest_job_failed`).
3. Re-run the count query:

   ```bash
   docker exec infra-db-1 psql -U postgres -d ai_mkt -c "
   SELECT 'ac_embeddings' AS name, COUNT(*) FROM ac_embeddings
   UNION ALL SELECT 'ec_embeddings', COUNT(*) FROM ec_embeddings;
   "
   ```

---

## 5. Collation warning (optional)

The warning `database "ai_mkt" has a collation version mismatch` is from switching Postgres images (e.g. to pgvector). It does **not** stop vector or embedding inserts. To clear it (optional):

```bash
docker exec infra-db-1 psql -U postgres -d ai_mkt -c "ALTER DATABASE ai_mkt REFRESH COLLATION VERSION;"
```

(Reconnect after; if you still see the warning, the OS/Postgres build may need to match the version the DB was created with.)

---

## Summary checklist

| Check | What it means |
|-------|----------------|
| **domain_ingest_job** has rows | Ingest was triggered at least once. |
| **domain_ingest_job.status = FAILED** | See **error_message** and worker logs. |
| **raw_page count = 0** | Fetch/ingest never succeeded or domain not allowed / excluded. |
| **sections > 0, ac_embeddings = 0** | index_ac failed (embedding API or earlier pgvector issue). |
| **Worker logs** | Show exact exception (domain_not_allowed, fetch error, embedding error, etc.). |
| **policy allowed_domains** | Domain you evaluate must be in this list. |

Start with the **domain_ingest_job** query and **worker logs**; they will usually point to the exact step where the flow fails.
