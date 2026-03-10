# Most Improved Domain — Feasibility & Placeholder

## 1. Feasibility result

**Not supported by current real data.**

To show “Most Improved Domain” with a real metric (e.g. “Attribution improved by X% since last evaluation”) we need:

- Per-domain metrics for the **current** evaluation run, and  
- Per-domain metrics for the **previous** evaluation run.

**What exists today:**

- **`GET /metrics/latest`** — Tenant-level KPIs only (no per-domain).
- **`GET /tenants/{tenantId}/domains`** — Per-domain `latest_rates`, but these are **all-time** aggregates (all `eval_result` rows per domain), not “last run only.” So we do not have “domain X in run N” vs “domain X in run N−1.”
- **`GET /eval/runs?limit=2`** — Only tenant-level `kpis_summary` per run; no per-domain breakdown.

The backend can compute per-domain metrics for a given run via `get_eval_metrics_for_run(tenant_id, run_id)`, but no dashboard API exposes **previous run per-domain** metrics. Therefore the frontend cannot compute “most improved domain” without either a new backend endpoint or fabricating data.

## 2. What was implemented (placeholder)

A **future-ready placeholder** was added so the section exists and can be filled when data is available:

- **Section:** “Most improved domain” card in the Executive Snapshot grid.
- **Design:** Dashed border, neutral gray styling so it is clearly not a live metric.
- **Copy:** “Per-domain comparison with the previous evaluation will appear here when supported.”
- **Design system:** Same grid and card pattern as “Top performer” and “Priority opportunity”; new card uses `border-dashed border-gray-300 bg-gray-50/60` and `TrendingUp` icon.

No fabricated historical per-domain metrics; no fake “X% improved” values.

## 3. Exact diff (summary)

**File:** `apps/dashboard/app/tenants/[tenantId]/overview/page.tsx`

- **Import:** Added `TrendingUp` from `lucide-react`.
- **Grid:** `xl:grid-cols-5` → `xl:grid-cols-6` (and `lg:grid-cols-3`) to accommodate the 6th card.
- **New card:** One new block after the “Priority opportunity” card:
  - Title: “Most improved domain” with `TrendingUp` icon.
  - Body: “Per-domain comparison with the previous evaluation will appear here when supported.”
  - Classes: `rounded-lg border border-dashed border-gray-300 bg-gray-50/60 p-3`.

## 4. Why the full feature was not implemented

- **Data:** There is no API that returns per-domain rates for the previous run. Domains list uses all-time aggregates; run history has only tenant-level KPIs.
- **Rule:** “No fabricated historical per-domain metrics” — so we do not invent deltas or “most improved” from current snapshot only.
- **Result:** Placeholder keeps the slot and wording grounded; real implementation requires backend support (e.g. endpoint returning current and previous run per-domain metrics).

## 5. Validation steps

1. **Build:** From repo root, run `pnpm build` (or your dashboard build command) and confirm no errors.
2. **UI:** Open Overview for a tenant that has at least one completed evaluation and domains. Confirm:
   - Executive Snapshot shows six cards, including “Most improved domain” with dashed border and the placeholder copy.
   - No real “X% improved” or domain name is shown in that card.
3. **Design:** Confirm the new card matches the existing card layout and does not use success/alert colors (so it is clearly a placeholder).
4. **Future:** When a backend endpoint exists that returns per-domain metrics for the last two runs, replace the placeholder body with logic that:
   - Computes per-domain deltas (e.g. attribution current vs previous),
   - Picks the domain with the largest improvement (safest metric: attribution),
   - Renders: “[domain]”, “[metric] improved by X% since last evaluation”.
