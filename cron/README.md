# AI-MKT Cron Jobs

Nightly eval, leakage checks, and anomaly detection. Can be scheduled via **systemd timers** or **crontab**.

---

## Required environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql://postgres:postgres@localhost:5432/ai_mkt` | Postgres connection string |
| `TENANTS` | Yes | — | Comma-separated tenant IDs (e.g. `tenant_a,tenant_b`) |
| `API_BASE` | Yes | `http://localhost:8000` | API base URL for `/answer` and `/retrieve/ac` |
| `EVAL_BEARER_TOKEN` | For leakage | — | Bearer token for API calls. Use `{tenant_id}` placeholder for per-tenant substitution |
| `EVAL_API_KEY` | Alternative | — | Fallback if `EVAL_BEARER_TOKEN` not set |
| `GIT_SHA` | No | — | Optional git SHA written to eval_run |
| `LOOKBACK_RUNS` | No | 10 | Eval runs to compare for anomaly detection |
| `REFUSAL_SPIKE_ABS` | No | 0.05 | Threshold for refusal_spike event |
| `CITATION_DROP_ABS` | No | 0.1 | Threshold for citation_drop event |
| `EVENT_COOLDOWN_HOURS` | No | 24 | Hours before re-inserting same event type |

---

## systemd timers (recommended)

Artifacts: `systemd/ai-mkt-{eval,leakage,anomaly}.service` and `.timer`.

### Prerequisites

- Repo at `/opt/ai-mkt` (or adjust paths in unit files)
- Virtualenv at `/opt/ai-mkt/.venv`
- User `ai-mkt` (and group) with read access to repo
- Env file: `/etc/ai-mkt/cron.env`

Example env file:

```bash
# /etc/ai-mkt/cron.env
DATABASE_URL=postgresql://user:pass@localhost:5432/ai_mkt
TENANTS=tenant_a,tenant_b
API_BASE=https://api.example.com
EVAL_BEARER_TOKEN=Bearer {tenant_id}
```

### Install

```bash
sudo cp systemd/ai-mkt-*.service systemd/ai-mkt-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

### Enable and start timers

```bash
# Enable all three timers (runs daily at 02:00 server time)
sudo systemctl enable ai-mkt-eval.timer ai-mkt-leakage.timer ai-mkt-anomaly.timer
sudo systemctl start ai-mkt-eval.timer ai-mkt-leakage.timer ai-mkt-anomaly.timer
```

### Check status

```bash
sudo systemctl list-timers ai-mkt-*
sudo journalctl -u ai-mkt-eval -u ai-mkt-leakage -u ai-mkt-anomaly -f
```

### Change schedule (default 02:00)

Override the timer schedule:

```bash
sudo systemctl edit ai-mkt-eval.timer
```

Add or replace:

```ini
[Timer]
OnCalendar=*-*-* 03:30:00
```

Reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ai-mkt-eval.timer
```

`OnCalendar` uses systemd time format (e.g. `03:30`, `Mon 02:00`, `*-*-15 02:00` for 15th of month).

### Eval 24/7 (hourly)

To run eval every hour so the Domains/Overview dashboard always has fresh metrics:

**systemd:** override the eval timer to run hourly:

```bash
sudo systemctl edit ai-mkt-eval.timer
```

Add or replace:

```ini
[Timer]
OnCalendar=hourly
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ai-mkt-eval.timer
```

**Crontab:** run every hour at minute 0:

```cron
0 * * * * cd /opt/ai-mkt && .venv/bin/python -m cron.eval_nightly
```

(Use a wrapper that sources your env file if needed.)

---

## Run manually

From the repo root, with venv activated:

```bash
cd /opt/ai-mkt
source .venv/bin/activate
export TENANTS=tenant_a,tenant_b
export DATABASE_URL=postgresql://...
export API_BASE=http://localhost:8000

python -m cron.eval_nightly
python -m cron.leakage_nightly
python -m cron.anomaly_detect
```

Or via systemd:

```bash
sudo systemctl start ai-mkt-eval.service
sudo systemctl start ai-mkt-leakage.service
sudo systemctl start ai-mkt-anomaly.service
```

Logs are written to `logs/cron_*.log` in the repo and to journald.

---

## Crontab fallback

If systemd timers are not available, add to crontab (`crontab -e`) as `ai-mkt`:

```cron
# Env (adjust values)
DATABASE_URL=postgresql://user:pass@localhost:5432/ai_mkt
TENANTS=tenant_a,tenant_b
API_BASE=https://api.example.com

# Daily at 02:00 (adjust path)
0 2 * * * cd /opt/ai-mkt && .venv/bin/python -m cron.eval_nightly
0 2 * * * cd /opt/ai-mkt && .venv/bin/python -m cron.leakage_nightly
0 2 * * * cd /opt/ai-mkt && .venv/bin/python -m cron.anomaly_detect
```

For env files, use a wrapper script that sources `/etc/ai-mkt/cron.env` then runs the python command.
