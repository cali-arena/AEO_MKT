# Commercial insight sections — implementation summary

## 1. Sections implemented

| Section | Status | Notes |
|--------|--------|-------|
| **Rename Composite Index → AI Visibility Score** | Implemented | KPI label and improvement summary copy only. |
| **Client Story Box** | Implemented | Existing headline block titled "Client summary"; same data (strongest, opportunity, health). |
| **Opportunity Impact** | Implemented | Citation-gap heuristic: domain with lowest citation + optional attribution focus; transparent copy. |
| **Monitoring Coverage** | Already present | Unchanged; "Monitoring coverage" in Portfolio Signals (X of Y domains completed, in progress, needs attention). |
| **Current vs previous evaluation** | Implemented | Replaces "Weekly Performance Summary" with safe "Current vs previous evaluation" (no weekly claim). |
| **Risk Monitor** | Implemented | At-risk count + list of domains with reason (low citation, weak attribution, hallucination risk, evaluation failed). |
| **KPI trend indicators** | Already present | Unchanged; each KpiCard already receives `trend` from `kpiTrends` (last 2 runs). |

---

## 2. Exact diff (summary)

**File:** `apps/dashboard/app/tenants/[tenantId]/overview/page.tsx`

- **KPI_ITEMS:** `label: "Composite index"` → `label: "AI Visibility Score"`.
- **improvementHighlights:** Summary string uses `"AI Visibility Score"` instead of `"composite index"` when referring to that metric.
- **Client summary:** The existing headline card now has a visible heading `"Client summary"` above the title and subtitle (same content).
- **atRiskDomains useMemo:** New. Builds list of up to 5 at-risk domains with reasons (from `withRates` by thresholds + failed domains with "evaluation failed").
- **evaluationComparison useMemo:** New. When `runHistory.runs.length >= 2`, returns current vs previous mention, citation, attribution and their deltas (from `trendPercent`).
- **New section "Commercial insights":** New heading + three cards:
  - **Opportunity impact** — Largest visibility gap (lowestCitation domain + rate); optional attribution focus (weakest domain); footnote "Based on current evaluation only."
  - **Risk monitor** — atRiskCount + atRiskDomains list (domain + reasons).
  - **Current vs previous evaluation** — When 2 runs: previous % → current % and delta for mention, citation, attribution; otherwise placeholder "Complete another evaluation to compare."

---

## 3. Data each section uses

| Section | Data source | Notes |
|--------|-------------|--------|
| **AI Visibility Score (rename)** | Same as before: `data.kpis.composite_index`, `runHistory.runs[0/1].kpis_summary.composite_index` for trend. | Display label and improvement summary text only. |
| **Client summary** | `executiveHeadline` (from `domainRows`, `best`, `weakest`, `strongCount`, `failedCount`, `runningCount`, `latestCompletedRun`). | No new API; existing headline block retitled. |
| **Opportunity impact** | `lowestCitation` (from `withRates` by min citation_rate), `weakest` (from `withRates` by min attribution_rate). `GET /tenants/{tenantId}/domains` → `latest_rates` per domain. | Transparent heuristic; no ROI or traffic. |
| **Monitoring coverage** | Already: `doneCount`, `domainRows.length`, `runningCount`, `failedCount` from `domainsData.domains`. | Unchanged. |
| **Current vs previous evaluation** | `GET /eval/runs?limit=2` → `runHistory.runs[0].kpis_summary`, `runHistory.runs[1].kpis_summary` (mention_rate, citation_rate, attribution_accuracy). Deltas via existing `trendPercent`. | Tenant-level KPIs only; no fabricated "weekly" cadence. |
| **Risk monitor** | `withRates` filtered by attribution &lt; 0.7, citation &lt; 0.7, hallucination &gt; 0.05; plus `domainRows` with `resolvedStatus === "FAILED"`. Same as `atRiskCount` logic. | All from `GET /tenants/{tenantId}/domains`. |
| **KPI trend indicators** | Already: `runHistory` (limit=2), `trendMapFromRuns(runHistory?.runs)` → `kpiTrends` passed to each KpiCard. | Unchanged. |

No new API endpoints. No fake ROI, traffic, leads, conversions, or indexed pages.

---

## 4. Validation steps

1. **Build:** From repo root run `pnpm build` (or your dashboard build). Confirm no errors.
2. **Overview with data:** Open Overview for a tenant with at least one completed evaluation and multiple domains.
   - **Client summary:** Card shows "Client summary" heading and the same one-line title + subtitle (strongest, opportunity, health).
   - **KPI row:** Fifth card label is "AI Visibility Score" (value and trend unchanged).
   - **Portfolio Signals:** "Improvement summary" can mention "AI Visibility Score" when that metric moved.
   - **Commercial insights:** Three cards:
     - Opportunity impact: domain with lowest citation named, rate shown; optional "Attribution focus: [weakest]"; footnote present.
     - Risk monitor: at-risk count; if any, list of domains with reasons (low citation, weak attribution, hallucination risk, evaluation failed), max 5.
     - Current vs previous evaluation: if 2+ runs, three lines "Previous % → Current % (delta%)"; else placeholder text.
3. **Overview with one run only:** Evaluation comparison card shows "Complete another evaluation to compare...". No crash.
4. **Overview with no at-risk domains:** Risk monitor shows "No domains currently at risk." and no list.
5. **Design:** Commercial insight cards use existing patterns (rounded-lg, border, shadow-sm); Opportunity = amber tint, Risk = rose tint, Evaluation = neutral gray. Layout: grid sm:grid-cols-2 lg:grid-cols-3.
