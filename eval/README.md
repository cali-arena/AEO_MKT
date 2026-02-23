# Eval Scripts & Datasets

## Quick start

```bash
# 1. Start API (required for harness)
uvicorn apps.api.main:app --reload

# 2. Run full eval (harness + metrics → eval/runs/latest/)
make eval
```

No make? Run the two commands under "Example" in eval/metrics.py section.

## Environment variables

| Var | Required | Description |
|-----|----------|-------------|
| `EVAL_BEARER_TOKEN` | No | Override auth: full Bearer token. Use `{tenant_id}` for per-query tenant. |
| `EVAL_API_KEY` | No | Same as Bearer token when API uses key auth. |
| `DATABASE_URL` | Yes (API) | Postgres. Default: `postgresql://postgres:postgres@localhost:5432/ai_mkt` |

Default auth: `Authorization: Bearer tenant:{tenant_id}` from each query row.

---

## queries_seed.jsonl

Domain-tagged query dataset for evaluation. Use for benchmarking retrieval, answer quality, or domain routing.

### Format

Each line is a JSON object with:

| Field     | Required | Description                                      |
|-----------|----------|--------------------------------------------------|
| query_id  | ✓        | Unique identifier (e.g. `q001`, `q042`)          |
| tenant_id | ✓        | Tenant scope (e.g. `mover_a`, `mover_b`)         |
| domain    | ✓        | Category tag for the query intent                |
| query     | ✓        | The natural-language question or request         |
| notes     |          | Optional annotation (e.g. "ambiguous short")     |

### Domains

- `services` – moving services, packing, specialty items, commercial moves
- `pricing` – costs, estimates, add-ons, surcharges, discounts
- `faq` – how it works, preparations, tips, prohibited items
- `coverage_area` – states, regions, international, rural
- `policies` – cancellation, payment, deposits, guarantees
- `claims_damage` – damage claims, lost items, valuation, liability
- `quotes_booking` – get quote, schedule, estimate, booking
- `contact_support` – phone, email, tracking, complaints, escalation

### Query Variety

- **Short:** `"Moving"`, `"Costs"`, `"Help"`
- **Long:** Multi-sentence, detailed scenarios (e.g. military PCS, office relocation)
- **Specific:** Concrete scenarios (e.g. 2BR apartment Chicago to Denver)
- **Ambiguous:** Minimal context (e.g. `"stuff"`, `"ballpark"`)
- **Policy-related:** Terms, liability, coverage, procedures

### Usage

```bash
# Count by domain
jq -s 'group_by(.domain) | map({domain: .[0].domain, count: length})' eval/queries_seed.jsonl

# Filter by tenant
jq -s 'map(select(.tenant_id == "mover_a"))' eval/queries_seed.jsonl
```

---

## eval/harness.py

Eval runner that calls `/answer` for each query in the dataset and saves JSONL results.

### CLI

| Arg | Default | Description |
|-----|---------|-------------|
| `--dataset` | `eval/queries_seed.jsonl` | Input JSONL path |
| `--base-url` | `http://localhost:8000` | API base URL |
| `--out-dir` | `eval/out` | Output directory |
| `--concurrency` | 1 | Max concurrent requests |
| `--timeout` | 60 | Request timeout (seconds) |

### Auth

Uses `Authorization: Bearer tenant:{tenant_id}` from each row's `tenant_id`. Override via env:

- `EVAL_BEARER_TOKEN` – full token (e.g. `tenant:mover_a` or `tenant:{tenant_id}`)
- `EVAL_API_KEY` – same as Bearer token when API uses key auth

### Output

Writes `{out-dir}/results.jsonl`. Each record: request fields + `refused`, `answer`, `claims`, `citations`, `evidence_ids`, `scores`, `latency_ms`, `run_meta`. On error: `error` field, no response fields.

Retries once on 5xx; failures are always recorded (never hidden).

### Example

```bash
# Start API first: uvicorn apps.api.main:app --reload

# Run harness (sequential, default)
python eval/harness.py --dataset eval/queries_seed.jsonl --base-url http://localhost:8000 --out-dir eval/out

# Run with concurrency and custom timeout
python eval/harness.py --dataset eval/queries_seed.jsonl --concurrency 4 --timeout 30
```

---

## eval/metrics.py

Compute eval metrics from `results.jsonl`. Outputs `metrics_overall.json`, `metrics_by_domain.json`, `worst_queries.json`.

### CLI

| Arg | Default | Description |
|-----|---------|-------------|
| `--in` | `eval/out/results.jsonl` | Input results path |
| `--out-dir` | `eval/out` | Output directory |

### Metrics

- **Mention/Answer Rate** – % of queries that got an answer (not refused)
- **Citation Rate** – % of answered queries with ≥1 citation
- **Attribution Accuracy proxy** – supported_claims / total_claims (claim evidence_ids all in citations)
- **Hallucination incidents** – answered queries with claims missing evidence_ids or referencing uncited IDs
- **Composite Visibility Index** – weighted 0–100 (answer + citation + attribution, minus hallucination penalty)

### Output (deterministic, sorted keys)

- `metrics_overall.json` – aggregates across all queries
- `metrics_by_domain.json` – same metrics per domain (sorted domain keys)
- `worst_queries.json` – top 10: refused, low-score answered, zero-citation answered

### Example

```bash
# Full pipeline via Makefile (writes to eval/runs/latest/)
make eval

# Or manually:
python eval/harness.py --dataset eval/queries_seed.jsonl --out-dir eval/runs/latest
python eval/metrics.py --in eval/runs/latest/results.jsonl --out-dir eval/runs/latest
```
