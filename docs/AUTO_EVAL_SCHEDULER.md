# Scheduled automatic domain reevaluation (auto-eval scheduler)

## 1. Implementation plan (summary)

- **Where:** Backend worker process (`apps/api/worker.py`) runs a daemon thread that executes one “tick” every `AUTO_EVAL_INTERVAL_MINUTES` (default 5).
- **What each tick does:** For each tenant (from `AUTO_EVAL_TENANTS` env or from `eval_domain` table), list monitored domains; for each domain skip if not indexed (index state not DONE) or if a PENDING/RUNNING eval job already exists; otherwise add to an eligible list. Enqueue a single `domain_eval_job` per tenant with that eligible list. Existing worker loop consumes these jobs via `claim_domain_eval_job` and runs the existing evaluation pipeline.
- **Overlap guard:** A non-blocking lock ensures only one tick runs at a time; if the previous cycle is still running, the next tick is skipped and logged.
- **Optional API:** `GET /scheduler/status` returns `enabled`, `interval_minutes`, `last_tick_at` (from `scheduler_state` table) for optional dashboard UI.
- **Frontend:** No change required for “latest completed results”; Overview already polls every 3s when any domain is EVALUATING and refetches `/metrics/latest` and domains. When scheduled runs complete, the next poll shows updated data.

## 2. Root cause / missing piece in the current system

- **Missing piece:** There was no server-side loop that periodically enqueued evaluation jobs for monitored domains. Manual “Run evaluation” (POST `/tenants/{tenant_id}/domains/evaluate`) and cron (e.g. `cron/eval_nightly`) existed, but no in-process scheduler with a configurable interval (e.g. 5 minutes) inside the worker.
- **Reused:** Existing `domain_eval_job` queue, `enqueue_domain_eval_job`, `claim_domain_eval_job`, `list_eval_domains`, `get_domain_index_state`, `is_index_up_to_date`, `get_pending_or_running_job_id_for_domain`, and the full eval pipeline. No change to evaluation architecture.

## 3. Exact diff by file

### `apps/api/services/repo.py`

- **Added** `list_tenant_ids() -> list[str]`: `SELECT DISTINCT tenant_id FROM eval_domain ORDER BY tenant_id`.
- **Added** `get_scheduler_last_tick() -> datetime | None`: read `last_tick_at` from `scheduler_state` (id=1).
- **Added** `set_scheduler_last_tick() -> None`: update `scheduler_state` set `last_tick_at = now()`, `updated_at = now()`.

### `apps/api/worker.py`

- **Imports:** `get_pending_or_running_job_id_for_domain` from `domain_jobs`; `list_tenant_ids`, `set_scheduler_last_tick` from `repo`.
- **Global:** `_SCHEDULER_LOCK = threading.Lock()`.
- **New** `_auto_eval_tick()`: if `AUTO_EVAL_ENABLED` not set, return; try acquire `_SCHEDULER_LOCK` (non-blocking); if failed, log `scheduler_skip_overlap` and return. Read `AUTO_EVAL_INTERVAL_MINUTES` (default 5) and tenant list from `AUTO_EVAL_TENANTS` or `list_tenant_ids()`. For each tenant: `list_eval_domains`; for each domain skip if not `is_index_up_to_date(state, desired)` or if `get_pending_or_running_job_id_for_domain`; else add to eligible; if eligible, `enqueue_domain_eval_job(tenant_id, eligible)` and log; then call `set_scheduler_last_tick()`. Release lock in `finally`.
- **New** `_scheduler_loop(interval_seconds)`: daemon loop that `_STOP.wait(timeout=interval_seconds)` then `_auto_eval_tick()` until `_STOP`.
- **main():** If `AUTO_EVAL_ENABLED` true, start a daemon thread running `_scheduler_loop(interval_seconds)` and log `scheduler_started`.

### `apps/api/routes/scheduler.py` (new file)

- **GET /status** (mounted at `/scheduler/status`): returns `{ "enabled": bool, "interval_minutes": int, "last_tick_at": str | null }` from env and `get_scheduler_last_tick()`.

### `apps/api/main.py`

- **Import** `scheduler` from `apps.api.routes`.
- **Include** `app.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])`.

### `alembic/versions/016_scheduler_state.py` (new migration)

- **upgrade:** create table `scheduler_state` with `id` (PK), `last_tick_at` (timestamptz), `updated_at` (timestamptz); insert one row `id=1`.
- **downgrade:** drop `scheduler_state`.

### `.env.example`

- **Added** comments and optional vars: `AUTO_EVAL_ENABLED`, `AUTO_EVAL_INTERVAL_MINUTES`, `AUTO_EVAL_TENANTS`.

## 4. Env vars added

| Variable | Required | Default | Description |
|----------|----------|---------|--------------|
| `AUTO_EVAL_ENABLED` | No | `false` | Set to `1`, `true`, or `yes` to enable the scheduler in the worker. |
| `AUTO_EVAL_INTERVAL_MINUTES` | No | `5` | Interval in minutes between scheduler ticks (min 1). |
| `AUTO_EVAL_TENANTS` | No | (from DB) | Comma-separated tenant IDs. If unset, worker uses `list_tenant_ids()` (all tenants with rows in `eval_domain`). |

## 5. Validation steps

- [ ] **Scheduler disabled by default:** With `AUTO_EVAL_ENABLED` unset or `0`, worker starts without starting the scheduler thread; no `scheduler_started` log.
- [ ] **Default interval 5 minutes:** With only `AUTO_EVAL_ENABLED=1`, logs show `scheduler_started interval_minutes=5`.
- [ ] **Monitored domains reevaluated every interval:** With scheduler enabled, add a monitored domain (indexed and DONE); within ~2× interval, logs show `scheduler_tick`, `scheduler_jobs_queued` for that tenant; worker picks the job and runs eval; Overview/Domains show updated metrics after completion.
- [ ] **No duplicate/overlapping runs:** While a tick is running (or many tenants), next tick skips with `scheduler_skip_overlap`. Domains with PENDING/RUNNING eval job are skipped (`scheduler_skipped_pending`); only one job per tenant per tick with no duplicate domains in that job.
- [ ] **Manual “Run evaluation” still works:** POST `/tenants/{tenant_id}/domains/evaluate` (single or all domains) still enqueues jobs; worker processes them; UI shows status and completion as before.
- [ ] **Overview and Domains reflect scheduled results:** After a scheduled run completes, refresh or wait for existing 3s poll; `/metrics/latest` and domains list show updated KPIs and per-domain rates.
- [ ] **Scheduler can be disabled:** Set `AUTO_EVAL_ENABLED=0` (or unset), restart worker; no scheduler thread, no ticks.
- [ ] **GET /scheduler/status:** Returns `enabled`, `interval_minutes`, and `last_tick_at` (ISO or null); `last_tick_at` updates after a tick when `scheduler_state` table exists and migration has run.

## 6. How to test locally

1. Start DB and run migrations: `alembic upgrade head` (so `scheduler_state` exists).
2. Set in `.env`: `AUTO_EVAL_ENABLED=1`, `AUTO_EVAL_INTERVAL_MINUTES=1` (or 5).
3. Start API and worker: e.g. `docker compose -f infra/docker-compose.yml --env-file .env up -d api worker` or run worker locally: `python -m apps.api.worker`.
4. Ensure at least one tenant has monitored domains (add via dashboard or API) and that those domains are indexed (DONE).
5. Watch worker logs for `scheduler_started`, then `scheduler_tick`, `scheduler_jobs_queued` (or `scheduler_skipped_*`), `scheduler_tick_done`.
6. Trigger manual “Run evaluation” from Domains page; confirm job runs and completes; confirm scheduler still runs on its interval without conflict.
7. Call `GET /scheduler/status`; confirm `enabled: true`, `interval_minutes`, and `last_tick_at` after a tick.
8. Open Overview/Domains; confirm metrics and domain table update after scheduled runs complete (and after 3s when EVALUATING).

## 7. How to test in deploy

1. Deploy with migration `016_scheduler_state` applied.
2. Set `AUTO_EVAL_ENABLED=1` and optionally `AUTO_EVAL_INTERVAL_MINUTES` and `AUTO_EVAL_TENANTS` in the worker (and API if same env) environment.
3. Restart worker so it picks up env and starts the scheduler thread.
4. Verify logs for `scheduler_started` and periodic `scheduler_tick` / `scheduler_tick_done`; confirm no overlapping ticks (`scheduler_skip_overlap` if a tick runs long).
5. Confirm dashboard Overview and Domains show updated data after scheduled evaluations complete; confirm manual “Run evaluation” still works.
6. To disable: set `AUTO_EVAL_ENABLED=0` (or remove), restart worker.

## 8. Deploy on VM (Docker Compose)

From the project root on the server (e.g. `~/AEO_MKT`):

```bash
ssh <server>
cd ~/AEO_MKT   # or your project path
git pull
docker compose -f infra/docker-compose.yml --env-file .env build
docker compose -f infra/docker-compose.yml --env-file .env up -d
```

To restart only API and worker after a code/config change:

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d --build api worker
```

Ensure `.env` (or the env file used by the worker) includes `AUTO_EVAL_ENABLED` and `AUTO_EVAL_INTERVAL_MINUTES` if you want the scheduler enabled. Run migration if not already applied: the API container runs `alembic upgrade head` on startup.

**Verify scheduler (when enabled):**

```bash
docker compose -f infra/docker-compose.yml logs -f worker
```

Expected log lines: `scheduler_started`, `scheduler_tick`, `scheduler_tick_done`; when jobs are enqueued: `scheduler_jobs_queued`; when domains are skipped: `scheduler_skipped_not_indexed` or `scheduler_skipped_pending`.

## 9. Risks / scaling concerns

- **Single worker:** With one worker process, one scheduler thread runs; lock prevents overlapping ticks. Multiple worker processes each run their own scheduler; all will tick on the same interval and may enqueue jobs for the same tenants. That can mean duplicate eval jobs (same tenant+domains) in the queue. Mitigation: `get_pending_or_running_job_id_for_domain` prevents enqueueing a domain that already has a PENDING/RUNNING job; so the second worker’s tick will skip those domains. If both ticks run at nearly the same time, both could enqueue before either job is claimed; then two jobs for the same tenant (possibly same domains) could exist. Acceptable for MVP; for strict single-job-per-tenant-per-interval, use a single worker or a distributed lock (e.g. DB or Redis) for the tick.
- **Many tenants / domains:** One tick iterates all tenants and all their domains; if the list is very large, the tick can run long and the next tick will skip (overlap). Eval jobs are queued and processed by existing worker concurrency; no change to job execution.
- **DB:** `list_tenant_ids()` and `get_domain_index_state` / `get_pending_or_running_job_id_for_domain` add read load every interval; minimal for typical tenant/domain counts.
- **Migration:** If `016_scheduler_state` is not applied, `set_scheduler_last_tick()` and `get_scheduler_last_tick()` may fail; worker logs `scheduler_state_update_skip` and continues; API returns `last_tick_at: null`; scheduler still runs.
