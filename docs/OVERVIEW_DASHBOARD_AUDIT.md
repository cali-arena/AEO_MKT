# AEO_MKT Frontend Dashboard Audit — Overview Page

**Objective:** Explain why the Overview page still feels weak, generic, and not commercially persuasive for client demos, and plan a safe refactor.

**Scope:** Frontend dashboard only. Backend behavior is taken as given.

---

## 1. FRONTEND FILE MAP

| File | Role |
|------|------|
| **Overview page** | |
| `apps/dashboard/app/tenants/[tenantId]/overview/page.tsx` | Main Overview UI. Fetches `/metrics/latest`, `GET /tenants/{tenantId}/domains`, `/eval/runs?limit=2`. Renders KPI row, Last run + Portfolio Summary card, Domain Performance table. Uses `resolveDomainStatus` / `resolvedStatusBadgeClass` from `domainStatus.ts`, `MetricBadge`, `KpiCard`, `LastRunPanel`. |
| **Layout & shell** | |
| `apps/dashboard/app/tenants/[tenantId]/layout.tsx` | Tenant shell: AuthGuard, TenantNav, Header, NotificationBanner, main with `max-w-6xl`. |
| `apps/dashboard/app/layout.tsx` | Root app layout (not tenant-specific). |
| `apps/dashboard/components/layout/TenantNav.tsx` | Sidebar nav (Overview, Domains, Trends, Worst Queries, Leakage) + HealthScore link. |
| `apps/dashboard/components/layout/Header.tsx` | Top bar: tenant label, env badge, “Last sync”, RunSelector. |
| `apps/dashboard/components/layout/NotificationBanner.tsx` | Fetches `/metrics/latest`; shows alerts when citation &lt; 70%, mention &lt; 50%, or hallucinations &gt; 0; links to Overview. |
| `apps/dashboard/components/layout/HealthScore.tsx` | Fetches `/metrics/latest`; derives score from `composite_index`; links to Overview. |
| `apps/dashboard/components/layout/RunSelector.tsx` | Fetches `/eval/runs?limit=15`; dropdown to switch run_id in URL (used on other pages, not by Overview content). |
| **Data & API** | |
| `apps/dashboard/lib/api.ts` | Single `apiFetch<T>(path, { tenantId })`; Bearer auth; no data hooks. |
| `apps/dashboard/lib/types.ts` | `MetricsLatestResponse`, `MetricsKPIs`, `DomainListItem`, `DomainsListResponse`, `EvalMetricsRates`, `EvalRunsResponse`, `EvalRunListItem`, etc. |
| `apps/dashboard/lib/domainStatus.ts` | `resolveDomainStatus(row)`, `resolvedStatusBadgeClass(status)`. Shared by Overview and Domains. |
| **Domains page (reference)** | |
| `apps/dashboard/app/tenants/[tenantId]/domains/page.tsx` | Full Domains workspace: list domains, add, run evaluation, retry, delete, drawer. Uses same `apiFetch`, `domainsPath`, `resolveDomainStatus`, `resolvedStatusBadgeClass`, `MetricBadge`. |
| **Reusable UI** | |
| `apps/dashboard/components/ui/KpiCard.tsx` | KPI card: label, value, format (percent/number/decimal), optional trend, accent, optional sparkline. |
| `apps/dashboard/components/ui/KpiCardSkeleton.tsx` | Skeleton for KPI cards. |
| `apps/dashboard/components/ui/LastRunPanel.tsx` | “Last run” card: created_at, crawl_policy_version, AC/EC hashes. |
| `apps/dashboard/components/ui/LastRunPanelSkeleton.tsx` | Skeleton for LastRunPanel. |
| `apps/dashboard/components/ui/MetricBadge.tsx` | Small badge for mention/citation/attribution/hallucination with color by threshold. |
| **Domains-specific** | |
| `apps/dashboard/components/domains/DomainDrawer.tsx` | Drawer with domain details and MetricBadges; used only on Domains page. |

**No dedicated data hooks:** Overview and Domains each use local `useState` + `useCallback` + `useEffect`; no shared `useOverviewData` or `useDomainsList`.

---

## 2. CURRENT DATA FLOW

**Overview today:**

1. **On mount (and when `tenantId` or `refreshOverview` refs change):**  
   `refreshOverview(false)` runs:
   - `loadMetrics(false)` → `GET /metrics/latest` with `tenantId` → `MetricsLatestResponse` (run metadata + `kpis` only; no per-domain).
   - `loadDomains(false)` → `GET /tenants/{tenantId}/domains` → `DomainsListResponse` (`domains: DomainListItem[]` with `latest_rates`, `ui_status`, `last_run_created_at`, etc.).
   - `loadRunHistory()` → `GET /eval/runs?limit=2` → `EvalRunsResponse` for KPI trend (current vs previous run).

2. **State:**  
   - `data` = `MetricsLatestResponse | null` (drives KPIs + LastRunPanel).  
   - `domainsData` = `DomainsListResponse | null` (drives Portfolio Summary + Domain Performance table).  
   - `runHistory` = used only for `trendMapFromRuns(runHistory?.runs)` → `kpiTrends` passed to `KpiCard` trend prop.

3. **Derived on the page:**  
   - `domainRows`: map `domainsData.domains` with `resolveDomainStatus(row)`, sorted by status then attribution.  
   - `doneCount` / `failedCount` / `runningCount` from `domainRows`.  
   - `withRates`, `best`, `weakest` from domains that have `latest_rates`.  
   - `kpiTrends` from last two runs.

4. **Refresh:**  
   - When any domain has `resolvedStatus === "EVALUATING"`, a 3s interval calls `refreshOverview(true)` (silent) until none are in progress.

**Endpoints used by Overview:**

- `GET /metrics/latest` → aggregate KPIs + run metadata only (no per_domain in this route; see backend).  
- `GET /tenants/{tenantId}/domains` → full per-domain list with status and rates (same as Domains page).  
- `GET /eval/runs?limit=2` → run list for trend deltas.

**Mappers:**  
- Raw API responses are used with typed interfaces; no separate mapper layer.  
- `resolveDomainStatus` / `resolvedStatusBadgeClass` turn API row into display status/badge (shared with Domains).  
- `formatDateTime` and `statusLabel` are local to the Overview page.

---

## 3. ROOT CAUSES (Why Overview Still Feels Generic / Weak)

**3.1 Primary source of truth is aggregate-only in the hero**  
- The first thing users see is a row of five KPI cards from `/metrics/latest` (mention rate, citation rate, attribution accuracy, hallucinations, composite index). These are **tenant-level aggregates** only.  
- The backend `GET /metrics/latest` (`apps/api/routes/metrics.py`) returns `MetricsLatestResponse` with no `per_domain`; domain-level value is not in that response.  
- So the “hero” of the page is generic portfolio numbers. Domain-level results appear only lower down, after a dense summary card and then a table. **Value is not front-and-center.**

**3.2 Information hierarchy favors ops over value**  
- Row 2 pairs “Last run” (created_at, crawl_policy_version, AC/EC hashes) with “Portfolio Performance Summary”.  
- LastRunPanel is **developer-oriented** (policy version, hashes). For a client demo, “when did we last evaluate?” is useful; “AC/EC version hashes” is not.  
- The summary card mixes useful stats (domains monitored, completed/running/failed, top performer, priority opportunity, portfolio health) with “Latest evaluation completed” and “Domain execution status” in a grid of six small tiles. **No single clear headline** (e.g. “3 of 5 domains healthy, 2 need attention”) and no strong visual anchor for “here’s your ROI.”

**3.3 Domain table is correct but not framed for sales**  
- The Domain Performance table reuses the same data and logic as Domains (same API, same `resolveDomainStatus`, same `MetricBadge`). So **data and source of truth are correct**.  
- But the table is a **dense grid** (Domain, Status, Mention, Citation, Attribution, Hallucination, Updated) with no executive summary above it (e.g. “2 top performers, 1 needs focus”), and the “Top” / “Needs focus” row styling, while present, doesn’t translate into a single “so what?” number or sentence.  
- Link to Domains is “View domain workspace →” which is operational, not value-oriented.

**3.4 Redundant / overlapping fetches**  
- Overview, NotificationBanner, and HealthScore each call `GET /metrics/latest` independently. That’s three calls for the same endpoint when viewing Overview. Not wrong, but no shared cache or hook, so the page doesn’t feel “one source of truth” from a code perspective.

**3.5 Copy and labels are mixed**  
- Some labels are client-friendly (“Executive snapshot”, “Top performer”, “Priority opportunity”, “Portfolio health”, “Healthy” / “Needs attention”).  
- Others are technical (“Last run”, “Crawl policy”, “AC / EC version”, “Domain execution status”, “Updated”).  
- “View domain workspace” is operator language. Inconsistent tone weakens the commercial feel.

**3.6 Layout constraint**  
- Tenant layout uses `max-w-6xl` for main content. For a wide table (7 columns), this can feel cramped and makes the table the dominant visual without a clear “headline” block that fits the width.

**3.7 No explicit “so what?” or ROI line**  
- The page shows numbers and statuses but doesn’t state one or two sentences such as: “Your visibility is strong on 3 domains; 2 domains need attention to improve attribution.” That kind of line is what makes an Overview feel commercially persuasive.

---

## 4. REUSABLE SOURCES OF TRUTH

**Already reused:**  
- **Domain list and metrics:** `GET /tenants/{tenantId}/domains` — same as Domains page. Overview already uses it.  
- **Status resolution:** `resolveDomainStatus` and `resolvedStatusBadgeClass` from `@/lib/domainStatus` — used by both Overview and Domains; keep using.  
- **Metric display:** `MetricBadge` for mention/citation/attribution/hallucination — same component and thresholds; values match Domains.  
- **Types:** `DomainListItem`, `DomainsListResponse`, `EvalMetricsRates`, `MetricsLatestResponse` from `@/lib/types` — no duplication.

**Can be reused or extracted:**  
- **Formatting:** `formatDateTime` is local to Overview; Domains uses ad-hoc `toLocaleString`. A small shared helper in `lib/format.ts` (e.g. `formatDateTime(iso)`) would keep consistency without changing behavior.  
- **Path helpers:** `domainsPath(tenantId)` is duplicated in Overview and Domains; could live in `lib/api.ts` or `lib/paths.ts` and be imported.  
- **Best/weakest logic:** Overview already computes `best` and `weakest` from `withRates` by attribution; this is the right metric for “top performer” / “priority opportunity” and can stay or move to a tiny util if Domains ever needs it.

**Not in backend for Overview:**  
- `GET /metrics/latest` does not return per_domain. Per-domain data correctly comes only from `GET /tenants/{tenantId}/domains`. Do not assume a different “overview” endpoint; keep using the domains list as the source for domain-level metrics.

---

## 5. UI / PRODUCT PROBLEMS (Client Demo / ROI / Commercial)

1. **No single “headline” outcome** — The page doesn’t open with one clear sentence (e.g. “4 of 5 domains are in good shape” or “Attribution improved 12% vs last run”).  
2. **Hero is aggregate-only** — Top KPIs are portfolio-level; they don’t answer “which domains are driving this?” or “where should we focus?”  
3. **Last run panel is dev-oriented** — Policy version and hashes don’t help a commercial story; “Last evaluated: date” does.  
4. **Summary is fragmented** — Six small tiles (latest eval, domains monitored, execution status, top performer, priority opportunity, portfolio health) spread attention; no one number or status dominates.  
5. **Domain table is not framed** — Table appears without a one-line summary (e.g. “2 top performers, 1 needs focus, 2 in progress”).  
6. **Terminology** — “Domain workspace”, “Domain execution status”, “Updated” feel operational; “Domains monitored”, “Top performer”, “Needs attention” are better for clients.  
7. **Weak “premium” feel** — No clear hierarchy (headline → key number → supporting table), and no deliberate use of space/typography to make the main message obvious.  
8. **Run selector not integrated** — Header RunSelector doesn’t drive Overview content; Overview always shows “latest” from its own fetches. So “run” is not part of the Overview story unless we explicitly add it later.

---

## 6. PROPOSED NEW OVERVIEW STRUCTURE

**Goal:** One clear headline, domain-level value first, then supporting detail. Executive-friendly and demo-ready.

**Suggested layout (conceptual):**

1. **Headline block (new)**  
   - One line: e.g. “4 of 5 domains healthy · 1 needs attention” or “All domains evaluated; portfolio attribution 87%.”  
   - Optional secondary: “Last evaluation: [date].”  
   - No hashes or policy version here.

2. **Key number row (elevate one metric)**  
   - Keep the five KPI cards but optionally add one **primary** metric (e.g. “Portfolio attribution” or “Composite score”) as a larger hero number with trend, so there’s a single number to point at in a demo.

3. **Domain snapshot (above the table)**  
   - Short sentence: “2 top performers, 1 priority opportunity, 2 in progress.” (derived from existing `domainRows` / `best` / `weakest`).  
   - Or a compact horizontal strip: [Top: domain A] [Needs focus: domain B] [In progress: 2].

4. **Last evaluation (simplified)**  
   - One card: “Last evaluation: [date/time]” and optionally “Run ID: …” for traceability. Move or drop “Crawl policy” and “AC/EC version” into a secondary/collapsible or remove from Overview.

5. **Domain Performance table (current, refined)**  
   - Keep: Domain, Status, Mention, Citation, Attribution, Hallucination, Updated.  
   - Keep: row styling (e.g. green for strong, red for weak), “Top” / “Needs focus” badges.  
   - Add: one-line summary above table (as in 3).  
   - CTA: “Manage domains” or “View all domains” instead of “View domain workspace”.

6. **Portfolio Summary (simplified)**  
   - Option A: Merge into “Domain snapshot” + “Last evaluation” so there’s no separate six-tile grid.  
   - Option B: Reduce to 3–4 tiles: Domains monitored, Healthy / Needs attention / In progress, Top performer, Priority opportunity (drop “Latest evaluation completed” and “Domain execution status” as separate tiles if they’re redundant with headline and table).

**Data:** No new APIs. Same `data` + `domainsData` + `runHistory`; derive headline and snapshot from `domainRows`, `doneCount`, `failedCount`, `runningCount`, `best`, `weakest`, and `data.created_at`.

---

## 7. SAFE IMPLEMENTATION PLAN

1. **Extract shared helpers (low risk)**  
   - Add `lib/format.ts` with `formatDateTime(iso)` (and optionally `formatDate(iso)`).  
   - Add `lib/paths.ts` (or keep in api) with `domainsPath(tenantId)`.  
   - Use them in Overview and optionally in Domains. No UI change.

2. **Add headline block (Overview only)**  
   - Above the KPI row, add a single line derived from `domainRows`: e.g. “X of Y domains healthy” and “Z need attention” when Z &gt; 0. Use existing counts.  
   - Add “Last evaluation: {formatDateTime(data.created_at)}” next to it or directly below.  
   - No new data; no backend change.

3. **Simplify Last run card**  
   - In `LastRunPanel` or via a prop, show “Last evaluation: [date]” as the main line.  
   - Move “Crawl policy” and “AC/EC version” to a “Details” expandable or smaller text, or limit to Overview-only variant (e.g. `variant="compact"`).  
   - Keeps traceability without dominating the panel.

4. **Add domain snapshot line above the table**  
   - One sentence: “2 top performers, 1 priority opportunity, 2 in progress” from `domainRows` / `best` / `weakest`.  
   - Place it between the “Domain Performance Overview” title and the table.

5. **Unify and client-friendly copy**  
   - Replace “View domain workspace →” with “Manage domains” or “View all domains”.  
   - Replace “Domain execution status” with “Status” or “Domain status” where it appears.  
   - Replace “Updated” with “Last evaluated” in table header if desired.  
   - Keep “Top performer” and “Priority opportunity” as-is.

6. **Optionally simplify Portfolio Summary**  
   - Reduce from six tiles to four: e.g. Domains monitored, Status (healthy / in progress / need attention), Top performer, Priority opportunity.  
   - “Latest evaluation completed” can be moved into the headline block; “Portfolio health” can be the same as “Status” or merged.  
   - Do this after headline + snapshot are in place so the summary doesn’t repeat the same info three times.

7. **Optional: hero KPI**  
   - If design allows, add one larger “Portfolio attribution” or “Composite score” card with trend, reusing existing `kpis` and `kpiTrends`.  
   - Low risk; only layout and emphasis.

8. **No RunSelector coupling in this phase**  
   - Overview continues to show latest run only. RunSelector can stay as-is for other pages.  
   - Later, if Overview should show a selected run, that would be a separate change (URL + fetch by run_id).

---

## 8. RISKS / EDGE CASES

- **Loading and partial state**  
  - Overview shows KPIs when `data` is set; domain section when `domainsData` is set. If `/metrics/latest` returns 404 but domains exist (or vice versa), one section can be empty or show “No completed evaluation” while the other has data. Keep existing empty/error handling; consider a short “Loading domain results…” so the table doesn’t flash empty then fill.

- **Stale data**  
  - Overview refreshes on mount and every 3s when any domain is EVALUATING. If a run completes and user doesn’t refresh, they see new data after at most 3s. If they leave the page and come back, they get a fresh load. No change needed unless you add explicit “Refresh” or longer polling.

- **Missing or inconsistent status**  
  - `resolveDomainStatus` prefers result-based signals (e.g. has results → DONE). If the API ever returns rows without `ui_status` or with unexpected values, badges still fall back to PENDING. Same behavior as Domains; no new risk if we only change copy and layout.

- **API mismatch**  
  - Domains list returns `last_run_created_at` per domain; Overview uses it for “Updated”. If a domain has no eval yet, `last_run_created_at` is null — we already show “—”.  
  - `GET /metrics/latest` 404: Overview already shows “No completed evaluation available yet.” and hides KPI row. Domain table can still show domains (from domains API); that’s correct.

- **Layout and width**  
  - `max-w-6xl` in layout affects all tenant pages. If the Domain Performance table feels too narrow, options are: allow horizontal scroll (current), or add a layout variant for Overview only (e.g. `max-w-7xl` for this route). Don’t change layout globally without checking other pages.

- **NotificationBanner / HealthScore**  
  - They each fetch `/metrics/latest`. If we later add a shared cache or React Query, we could deduplicate; for this refactor, leaving them as-is is safe.

---

## SUCCESS CRITERIA (Checklist)

After refactor:

- [ ] **Domain-level value is obvious** — Headline or first line answers “How many domains are healthy / need attention?”  
- [ ] **Client-facing** — No developer-only copy in the main view; “Last evaluation” preferred over “Crawl policy / AC/EC version” in hero.  
- [ ] **Premium feel** — Clear hierarchy: headline → key numbers → domain snapshot → table.  
- [ ] **Demo/sales ready** — One number or one sentence can be used to say “Here’s your visibility/ROI.”  
- [ ] **Reuse** — Overview still uses same APIs and shared `domainStatus` + `MetricBadge`; no new backend; values match Domains page.

---

*End of audit. No implementation was performed; all conclusions are based on the current codebase.*
