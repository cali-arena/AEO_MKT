# Full Stack Verification Report

## A) Exact Commands (from repo inspection)

```bash
# 1. Copy env
cp .env.example .env
# Edit .env: POSTGRES_PASSWORD, CORS_ALLOW_ORIGINS (include http://localhost:3000), EMBED_PROVIDER=deterministic for smoke

# 2. Start Postgres + API (requires Docker running)
docker compose -f infra/docker-compose.yml up -d

# 3. Migrations run automatically in api container (alembic upgrade head in CMD)

# 4. Seed fake eval data (requires API/Postgres up; or: make seed)
python scripts/dev_seed_eval.py
# Or run in container (avoids ensure_tables conflict with migrated schema):
# make seed

# 5. Smoke test API
curl -s http://localhost:8000/health
curl -s -H "Authorization: Bearer tenant:coast2coast" http://localhost:8000/metrics/latest
curl -s -H "Authorization: Bearer tenant:coast2coast" http://localhost:8000/leakage/latest

# 6. Run eval harness
docker compose -f infra/docker-compose.yml run --rm -e TENANTS=coast2coast -e API_BASE=http://api:8000 api python -m cron.eval_nightly

# 7. Start dashboard
cd apps/dashboard
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev

# 8. Run tests
pytest -q
```

## B) Environment Blocked: Docker Not Running

**Error:** `open //./pipe/dockerDesktopLinuxEngine: O sistema não pode encontrar o arquivo especificado`  
Docker Desktop must be started for `docker compose up` to work.

**Workaround:** Start Docker Desktop (Windows) or Docker daemon (Linux/Mac), then run the commands above.

## C) API Endpoints (tenant from auth only)

| Endpoint | Auth | Expected |
|----------|------|----------|
| GET /health | none | `{ok, version, time}` |
| GET /metrics/latest | Bearer tenant:X | MetricsLatestResponse or 404 |
| GET /metrics/trends?days=30 | Bearer tenant:X | MetricsTrendsResponse |
| GET /eval/runs?limit=20 | Bearer tenant:X | EvalRunsResponse |
| GET /eval/runs/{run_id}/results | Bearer tenant:X | EvalRunResultsResponse |
| GET /leakage/latest | Bearer tenant:X | LeakageLatestResponse |
| GET /monitor/leakage/latest | Bearer tenant:X | LeakageLatestResponse (same) |

## D) Files Added/Modified

1. **`.env`** – Created for local dev (DATABASE_URL, CORS_ALLOW_ORIGINS, EMBED_PROVIDER)
2. **`infra/.env`** – Created for compose variable substitution (POSTGRES_PASSWORD)
3. **`scripts/dev_seed_eval.py`** – New script to seed eval_run + 5 eval_results for tenant coast2coast, domain example.com
4. **`eval/queries_seed.jsonl`** – Added 5 coast2coast queries (cc_q1–cc_q5) so `make eval TENANT=coast2coast` works

## E) Test Results (without Docker/Postgres)

- **pytest -q**: Exit 0. 60+ tests skipped (Postgres not running). All non-DB tests passed.
- **No-network regression**: Pass
- **Contract shape tests**: Pass
- **Cache key prod safety**: Pass
- **Leakage route alias**: Pass
- **Dashboard build**: Success

## F) What Remains (when Docker is available)

1. Start Docker Desktop (required first).
2. Bring up Postgres + API.
3. Seed eval data.
4. Smoke test the API.
5. Run eval harness.
6. Start the dashboard.
7. Open pages in the browser.

## G) Step-by-step commands (run each in terminal; use separate terminals for long-running steps)

**Step 1 – Start Docker Desktop**

Start Docker Desktop before running any commands below.

---

**Step 2 – Bring up services**

```bash
docker compose -f infra/docker-compose.yml up -d
```

---

**Step 3 – Seed eval data**

```bash
python scripts/dev_seed_eval.py
```

---

**Step 4 – Smoke test API (run each separately)**

```bash
curl -s http://localhost:8000/health
```

```bash
curl -s -H "Authorization: Bearer tenant:coast2coast" http://localhost:8000/metrics/latest
```

```bash
curl -s -H "Authorization: Bearer tenant:coast2coast" http://localhost:8000/leakage/latest
```

---

**Step 5 – Run eval harness**

```bash
make eval TENANT=coast2coast
```

---

**Step 6 – Start dashboard (run in a separate terminal; keep it running)**

```bash
cd apps/dashboard
```

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

---

**Step 7 – Open pages in the browser**

- http://localhost:3000/login  
- http://localhost:3000/tenants/coast2coast/overview  
- http://localhost:3000/tenants/coast2coast/domains  
- http://localhost:3000/tenants/coast2coast/trends  
- http://localhost:3000/tenants/coast2coast/worst-queries  
- http://localhost:3000/tenants/coast2coast/leakage  
