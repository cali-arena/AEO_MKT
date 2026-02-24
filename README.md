# AI MKT

FastAPI backend for retrieve/answer, Next.js dashboard, and nightly eval/leakage jobs.

**Repo root:** `infra/docker-compose.yml`, `Makefile`, `.env.example`, `README.md` (this file).

---

## 1. Local dev quickstart

```bash
# Clone and enter repo
cd AI_MKT

# Create venv and install deps
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start Postgres only (API runs on host)
docker compose -f infra/docker-compose.yml up -d postgres

# Run API (hot reload)
uvicorn apps.api.main:app --reload

# In another terminal: ingest a page, run eval, run tests
make ingest TENANT=A URL=https://example.com
make eval TENANT=mover_a   # requires API + queries_seed.jsonl for tenant
export DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:5432/ai_mkt_test
make test
```

**Start full stack (Postgres + API in Docker)** — use when the dashboard shows "Failed to fetch" / `ERR_CONNECTION_REFUSED`:

```bash
make serve   # or: make up
```

Windows (PowerShell) without `make`:

```powershell
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
```

- API: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Postgres: `localhost:5432` (user/pass default: postgres/postgres)

---

## 2. Schema authority (IMPORTANT)

**Use ONE approach for prod and tests. Do not mix.**

| Authority | Command | When to use |
|-----------|---------|-------------|
| **Alembic (recommended)** | `alembic upgrade head` or `make migrate` | Default. Use for prod and tests. |
| ensure_tables | `ensure_tables()` in code (tests only, via `SCHEMA_AUTHORITY=ensure_tables`) | Optional test-only path. |

- **Production:** Always use Alembic. The API container runs `alembic upgrade head` on startup.
- **Tests:** Default is Alembic. Set `DATABASE_TEST_URL` (e.g. `postgresql://.../ai_mkt_test`); schema reset uses the same authority.
- Do not run Alembic and ensure_tables in the same session or on the same DB.

---

## 3. Testing

Tests use a separate `*_test` database to avoid polluting your dev DB. Set `DATABASE_TEST_URL` (or `DATABASE_URL_TEST`) before running:

```bash
export DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:5432/ai_mkt_test
make test
```

On Windows (PowerShell):

```powershell
$env:DATABASE_URL_TEST="postgresql://postgres:postgres@localhost:5432/ai_mkt_test"
make test
```

- Postgres must be running (`make up` or `docker compose -f infra/docker-compose.yml up -d postgres`).
- Schema is applied via Alembic migrations.
- Optional: `RESET_TEST_DB=1` drops and recreates the test schema before running.

---

## 4. VPS setup (Docker + Compose)

### 4.1 Prerequisites

- Docker and Docker Compose v2
- Domain pointing to VPS (for API, e.g. `api.yourvps.com`)

### 4.2 Copy env and set secrets

On the VM (or locally for full stack):

```bash
cd /root/AEO_MKT   # or your repo path
cp .env.example .env
```

Edit `.env` and set:

- `POSTGRES_PASSWORD` – strong password (required in prod)
- `POSTGRES_DB=ai_mkt` – database name (default; created automatically on first start)
- `CORS_ALLOW_ORIGINS` – your Vercel URL + localhost, comma-separated, no trailing slash  
  Example: `https://your-app.vercel.app,http://localhost:3000`
- `DATABASE_URL` – must use host `postgres` and the **same** password:  
  `postgresql://postgres:YOUR_PASSWORD@postgres:5432/ai_mkt`

### 4.3 One-time: create database on VM

The database **`ai_mkt`** is created automatically by the Postgres container when you first start the stack **with** `--env-file .env`. If the stack was ever started without it, re-create the volume so Postgres initializes with the correct password:

```bash
cd /root/AEO_MKT
docker compose -f infra/docker-compose.yml --env-file .env down -v
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
```

- `down -v` removes the Postgres data volume so the next `up` runs init (creates `ai_mkt`, runs `init.sql` for pgvector, then Alembic runs migrations).
- **Always** use `--env-file .env` for every compose command so `POSTGRES_PASSWORD` is set and you don’t see the “variable is not set” warning.

### 4.4 Start stack and run commands (no warning)

**Start:**

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
```

**Or use the helper script** (run from repo root; on VM run `chmod +x scripts/compose.sh` once):

```bash
./scripts/compose.sh up -d --build
./scripts/compose.sh logs -f api
./scripts/compose.sh ps
```

Using the script or always passing `--env-file .env` avoids the `POSTGRES_PASSWORD` warning and keeps the database and API in sync.

**If you see `password authentication failed for user "postgres"`:** Run the one-time steps in 4.3 (`down -v` then `up` with `--env-file .env`).

### 4.4 Run migrations

```bash
make migrate
```

### 4.5 Verify

```bash
curl -s http://localhost:8000/health
```

Expected: `{"ok": true, "version": "dev", "time": "2025-01-15T12:00:00.000000+00:00"}` (version from GIT_SHA or "dev").

### 4.6 Container status

```bash
make ps
make logs   # tail api logs
```

---

## 3. Vercel setup

### 3.1 Environment variable

In Vercel project settings → Environment Variables:

| Name | Value |
|------|-------|
| `NEXT_PUBLIC_API_BASE` | `https://api.yourvps.com` (no trailing slash) |

Copy from `apps/dashboard/.env.example` if needed.

### 5.2 Deploy dashboard

```bash
cd apps/dashboard
npm install
npm run build
```

Deploy via Vercel CLI or Git integration:

```bash
vercel
```

Or connect the repo and set root directory to `apps/dashboard`.

---

## 6. First tenant bootstrap

### 6.1 Policy

Ensure `policy/policy.json` has your tenant and `allowed_domains`:

```json
{
  "tenant_id": "coast2coast",
  "allowed_domains": ["coasttocoastmovers.com", "quote.unitedglobalvanline.com"],
  ...
}
```

### 6.2 Ingest content

```bash
make ingest TENANT=coast2coast URL=https://coasttocoastmovers.com/services
```

Add more URLs as needed. Each URL runs the full pipeline: crawl → ingest → sectionize → index_ac.

### 5.3 Run eval (optional)

Requires `eval/queries_seed.jsonl` with rows for your tenant, and API running.

```bash
make eval TENANT=mover_a
```

### 6.4 Open dashboard

- Eval runs: `/eval` (or equivalent dashboard route)
- Monitor events: `/monitor`

---

## 6. Nightly jobs

### 6.1 Run manually

With API running:

```bash
make eval TENANT=mover_a
make leakage TENANTS=mover_a,mover_b
```

### 6.2 Scheduled (systemd or cron)

See **[cron/README.md](cron/README.md)** for:

- systemd timers (eval, leakage, anomaly)
- Crontab fallback
- Required env: `TENANTS`, `API_BASE`, `DATABASE_URL`, optionally `EVAL_BEARER_TOKEN`

---

## 8. Troubleshooting

### CORS errors

- Ensure `CORS_ALLOW_ORIGINS` in `.env` includes your frontend origin exactly (no trailing slash).
- Example: `https://your-app.vercel.app,http://localhost:3000`
- Restart API after changing: `make down && make up`

### Password authentication failed for user "postgres"

- **Cause:** Postgres was first started without `--env-file .env` (or with empty `POSTGRES_PASSWORD`), so the data volume was initialized with a different password. The API uses the password from `.env`, so they don’t match.
- **Fix:** Remove the Postgres volume and start again with `.env` (all DB data will be lost):
  ```bash
  cd /path/to/repo
  docker compose -f infra/docker-compose.yml --env-file .env down -v
  docker compose -f infra/docker-compose.yml --env-file .env up -d --build
  ```
- **Prevent:** Always run compose with `--env-file .env` so both postgres and api use the same `POSTGRES_PASSWORD`.

### DB connection refused

- Postgres must be healthy before API starts. Check: `make ps` and `docker compose -f infra/docker-compose.yml logs postgres`
- In Docker: `DATABASE_URL` must use host `postgres`, not `localhost`
- On host (local dev): use `localhost` in `DATABASE_URL`

### Migrations fail

- Ensure Postgres is up and `DATABASE_URL` is correct
- Run: `make migrate`
- If schema is out of sync: `alembic upgrade head` (or `make migrate`)

### Eval/leakage return no data or fail

- API must be running (`make up`) – these scripts call the API over HTTP
- `TENANTS` must match tenant IDs in `queries_seed.jsonl` (eval) or your config (leakage)
- For leakage: set `EVAL_BEARER_TOKEN` or `EVAL_API_KEY` if your API requires auth

---

## Endpoints

- `GET /health` – Health check (no auth)
- `POST /retrieve/ac` – AC retrieval (vector + BM25)
- `POST /retrieve/ec` – EC retrieval (entity search)
- `POST /answer` – Grounded answer
- `GET /leakage/latest` – Leakage status (preferred)
- `GET /monitor/leakage/latest` – Leakage status (compat / legacy)

All except `/health` require: `Authorization: Bearer tenant:TENANT_ID`

### Leakage

```bash
# Preferred alias
curl -s -X GET "http://localhost:8000/leakage/latest" \
  -H "Authorization: Bearer tenant:my_tenant"

# Legacy
curl -s -X GET "http://localhost:8000/monitor/leakage/latest" \
  -H "Authorization: Bearer tenant:my_tenant"
```

Response: `{"tenant_id": "my_tenant", "ok": true, "last_checked_at": "2025-01-15T12:00:00+00:00", "details_json": null}` (or details from last pass/fail)

## Make targets

| Target | Description |
|--------|-------------|
| `make up` | Start docker compose (detached) |
| `make down` | Stop compose |
| `make logs` | Tail api logs |
| `make migrate` | Run alembic upgrade head |
| `make ingest TENANT=x URL=u` | Run pipeline for one URL |
| `make eval TENANT=x` | Run eval_nightly once |
| `make leakage TENANTS=a,b` | Run leakage_nightly once |
| `make test` | Run pytest |
| `make ps` | Container status |
| `make smoke` | Smoke test (health, metrics, eval, leakage); API must use EMBED_PROVIDER=deterministic |
