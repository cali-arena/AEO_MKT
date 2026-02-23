# AI-MKT Makefile. Run from repo root.
# Compose file: infra/docker-compose.yml

COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: up down serve logs migrate ingest eval leakage test ps smoke seed

up:
	$(COMPOSE) up -d

# Alias for up: start Postgres + API (API on localhost:8000). Use when make is available.
# Windows without make: docker compose -f infra/docker-compose.yml up -d
serve: up

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api

migrate:
	$(COMPOSE) run --rm api alembic upgrade head

# Ingest: run Day 1 pipeline (crawl, ingest, sectionize, index_ac) for one URL.
# Usage: make ingest TENANT=coast2coast URL=https://example.com/page
ingest:
	@test -n "$(TENANT)" || (echo "TENANT required. Usage: make ingest TENANT=x URL=https://..."; exit 1)
	@test -n "$(URL)" || (echo "URL required. Usage: make ingest TENANT=x URL=https://..."; exit 1)
	$(COMPOSE) run --rm api python -m apps.api.services.pipeline --tenant "$(TENANT)" --url "$(URL)"

# Eval: run eval_nightly once, writing to DB. Requires API running (make up).
# Usage: make eval TENANT=mover_a
eval:
	@test -n "$(TENANT)" || (echo "TENANT required. Usage: make eval TENANT=mover_a"; exit 1)
	$(COMPOSE) run --rm -e TENANTS="$(TENANT)" -e API_BASE="http://api:8000" api python -m cron.eval_nightly

# Leakage: run leakage_nightly once. Requires API running (make up).
# Usage: make leakage TENANTS=mover_a,mover_b
leakage:
	@test -n "$(TENANTS)" || (echo "TENANTS required. Usage: make leakage TENANTS=a,b"; exit 1)
	$(COMPOSE) run --rm -e TENANTS="$(TENANTS)" -e API_BASE="http://api:8000" api python -m cron.leakage_nightly

# Full test: pytest (uses test DB), smoke, leakage. Requires API running (make up) for smoke + leakage.
# Requires DATABASE_URL_TEST to avoid polluting dev DB. Example:
#   export DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:5432/ai_mkt_test
#   make test
test:
	@test -n "$(DATABASE_URL_TEST)" || (echo "DATABASE_URL_TEST required. export DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:5432/ai_mkt_test"; exit 1)
	ENV=test PYTEST_RUNNING=1 DATABASE_URL_TEST="$(DATABASE_URL_TEST)" pytest -q && $(MAKE) smoke && $(MAKE) leakage TENANTS=mover_a,mover_b

ps:
	$(COMPOSE) ps

# Seed: insert fake eval_run + eval_results for coast2coast. Run after make up.
seed:
	$(COMPOSE) run --rm api python scripts/dev_seed_eval.py

# Smoke: verify production shape (health, metrics, eval_run, leakage monitor_event).
# Requires API running (make up). Use EMBED_PROVIDER=deterministic to avoid HuggingFace.
smoke:
	$(COMPOSE) run --rm -e API_BASE="http://api:8000" -e EMBED_PROVIDER=deterministic api python scripts/smoke_prod.py
