"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle,
  BarChart3,
  Clock3,
  Globe2,
  Trophy,
} from "lucide-react";

import { KpiCard } from "@/components/ui/KpiCard";
import { KpiCardSkeleton } from "@/components/ui/KpiCardSkeleton";
import { MetricBadge } from "@/components/ui/MetricBadge";
import { apiFetch, ApiError } from "@/lib/api";
import { resolveDomainStatus, resolvedStatusBadgeClass } from "@/lib/domainStatus";
import type {
  DomainListItem,
  DomainsListResponse,
  EvalRunListItem,
  EvalRunsResponse,
  MetricsLatestResponse,
} from "@/lib/types";

type TrendMap = Partial<Record<keyof import("@/lib/types").MetricsKPIs, number | null>>;

const KPI_ITEMS: Array<{
  key: keyof import("@/lib/types").MetricsKPIs;
  label: string;
  format: "percent" | "number" | "decimal";
  accent?: "primary" | "success" | "warning" | "error" | "neutral";
}> = [
  { key: "mention_rate", label: "Mention rate", format: "percent", accent: "primary" },
  { key: "citation_rate", label: "Citation rate", format: "percent", accent: "primary" },
  { key: "attribution_accuracy", label: "Attribution accuracy", format: "percent", accent: "success" },
  { key: "hallucinations", label: "Hallucinations", format: "number", accent: "error" },
  { key: "composite_index", label: "Composite index", format: "decimal", accent: "primary" },
];

function domainsPath(tenantId: string): string {
  return `/tenants/${encodeURIComponent(tenantId)}/domains`;
}

function evalRunsPath(limit = 2): string {
  return `/eval/runs?limit=${limit}`;
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "--";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function statusLabel(status: "PENDING" | "EVALUATING" | "DONE" | "FAILED"): string {
  if (status === "DONE") return "Healthy";
  if (status === "FAILED") return "Needs attention";
  if (status === "EVALUATING") return "In progress";
  return "Pending";
}

function trendPercent(current: number, previous: number, invertDirection = false): number | null {
  if (!Number.isFinite(current) || !Number.isFinite(previous)) return null;
  if (previous === 0) return null;
  const raw = ((current - previous) / Math.abs(previous)) * 100;
  return invertDirection ? -raw : raw;
}

function trendMapFromRuns(runs: EvalRunListItem[] | null | undefined): TrendMap {
  if (!runs || runs.length < 2) return {};
  const latest = runs[0]?.kpis_summary;
  const previous = runs[1]?.kpis_summary;
  if (!latest || !previous) return {};
  return {
    mention_rate: trendPercent(latest.mention_rate, previous.mention_rate),
    citation_rate: trendPercent(latest.citation_rate, previous.citation_rate),
    attribution_accuracy: trendPercent(latest.attribution_accuracy, previous.attribution_accuracy),
    hallucinations: trendPercent(latest.hallucinations, previous.hallucinations, true),
    composite_index: trendPercent(latest.composite_index, previous.composite_index),
  };
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

export default function OverviewPage() {
  const params = useParams();
  const tenantId = params?.tenantId as string | undefined;

  const [data, setData] = useState<MetricsLatestResponse | null>(null);
  const [domainsData, setDomainsData] = useState<DomainsListResponse | null>(null);
  const [runHistory, setRunHistory] = useState<EvalRunsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [domainsLoading, setDomainsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<number | null>(null);

  const loadMetrics = useCallback(
    async (silent = false) => {
      if (!tenantId) return;
      if (!silent) setLoading(true);
      try {
        const res = await apiFetch<MetricsLatestResponse>("/metrics/latest", { tenantId });
        setData(res);
        setError(null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setData(null);
          setError(null);
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load metrics");
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [tenantId]
  );

  const loadDomains = useCallback(
    async (silent = false) => {
      if (!tenantId) return;
      if (!silent) setDomainsLoading(true);
      try {
        const res = await apiFetch<DomainsListResponse>(domainsPath(tenantId), { tenantId });
        setDomainsData({ ...res, domains: res.domains ?? [] });
      } catch {
        setDomainsData(null);
      } finally {
        if (!silent) setDomainsLoading(false);
      }
    },
    [tenantId]
  );

  const loadRunHistory = useCallback(
    async () => {
      if (!tenantId) return;
      try {
        const res = await apiFetch<EvalRunsResponse>(evalRunsPath(2), { tenantId });
        setRunHistory(res);
      } catch {
        setRunHistory(null);
      }
    },
    [tenantId]
  );

  const refreshOverview = useCallback(
    async (silent = false) => {
      await Promise.all([loadMetrics(silent), loadDomains(silent), loadRunHistory()]);
      setLastRefreshedAt(Date.now());
    },
    [loadDomains, loadMetrics, loadRunHistory]
  );

  useEffect(() => {
    if (!tenantId) return;
    refreshOverview(false);
  }, [tenantId, refreshOverview]);

  const domainRows = useMemo(() => {
    const rows = (domainsData?.domains ?? []).map((row) => {
      const resolvedStatus = resolveDomainStatus(row);
      return {
        ...row,
        resolvedStatus,
      };
    });

    const statusRank: Record<string, number> = {
      FAILED: 0,
      EVALUATING: 1,
      PENDING: 2,
      DONE: 3,
    };

    return rows.sort((a, b) => {
      const sr = (statusRank[a.resolvedStatus] ?? 99) - (statusRank[b.resolvedStatus] ?? 99);
      if (sr !== 0) return sr;
      const left = a.latest_rates?.attribution_rate ?? -1;
      const right = b.latest_rates?.attribution_rate ?? -1;
      if (left !== right) return left - right;
      return a.domain.localeCompare(b.domain);
    });
  }, [domainsData?.domains]);

  const doneCount = domainRows.filter((d) => d.resolvedStatus === "DONE").length;
  const failedCount = domainRows.filter((d) => d.resolvedStatus === "FAILED").length;
  const runningCount = domainRows.filter((d) => d.resolvedStatus === "EVALUATING").length;

  const hasInFlightRows = domainRows.some((d) => d.resolvedStatus === "EVALUATING");

  useEffect(() => {
    if (!tenantId || !hasInFlightRows) return;
    const interval = window.setInterval(() => {
      refreshOverview(true);
    }, 3000);
    return () => window.clearInterval(interval);
  }, [tenantId, hasInFlightRows, refreshOverview]);

  const withRates = domainRows.filter(
    (d): d is DomainListItem & {
      resolvedStatus: "PENDING" | "EVALUATING" | "DONE" | "FAILED";
      latest_rates: NonNullable<DomainListItem["latest_rates"]>;
    } => d.latest_rates != null
  );

  const best =
    withRates.length > 0
      ? withRates.reduce((a, b) =>
          a.latest_rates.attribution_rate >= b.latest_rates.attribution_rate ? a : b
        )
      : null;

  const weakest =
    withRates.length > 0
      ? withRates.reduce((a, b) =>
          a.latest_rates.attribution_rate <= b.latest_rates.attribution_rate ? a : b
        )
      : null;

  const latestCompletedRun = data?.created_at ?? null;
  const kpiTrends = trendMapFromRuns(runHistory?.runs);
  const strongCount = withRates.filter(
    (d) => d.latest_rates.attribution_rate >= 0.9 && d.latest_rates.hallucination_rate <= 0.01
  ).length;
  const lowestCitation =
    withRates.length > 0
      ? withRates.reduce((a, b) =>
          a.latest_rates.citation_rate <= b.latest_rates.citation_rate ? a : b
        )
      : null;
  const lowAttributionCount = withRates.filter((d) => d.latest_rates.attribution_rate < 0.7).length;
  const atRiskCount = domainRows.filter((d) => {
    if (d.resolvedStatus === "FAILED") return true;
    if (!d.latest_rates) return false;
    return (
      d.latest_rates.attribution_rate < 0.7 ||
      d.latest_rates.citation_rate < 0.7 ||
      d.latest_rates.hallucination_rate > 0.05
    );
  }).length;
  const highPerformingCount = withRates.filter(
    (d) =>
      d.latest_rates.attribution_rate >= 0.9 &&
      d.latest_rates.citation_rate >= 0.9 &&
      d.latest_rates.hallucination_rate <= 0.01
  ).length;
  const stableCount = withRates.filter((d) => {
    const isHigh =
      d.latest_rates.attribution_rate >= 0.9 &&
      d.latest_rates.citation_rate >= 0.9 &&
      d.latest_rates.hallucination_rate <= 0.01;
    if (isHigh) return false;
    return (
      d.latest_rates.attribution_rate >= 0.75 &&
      d.latest_rates.citation_rate >= 0.75 &&
      d.latest_rates.hallucination_rate <= 0.05
    );
  }).length;

  const improvementHighlights = useMemo(() => {
    if (!kpiTrends || Object.keys(kpiTrends).length === 0) {
      return {
        summary: "Complete another evaluation to see comparison with this run.",
        tone: "neutral" as const,
      };
    }
    const improved: string[] = [];
    const declined: string[] = [];
    const addSignal = (label: string, delta: number | null | undefined) => {
      if (delta == null) return;
      if (delta >= 0.1) improved.push(label);
      else if (delta <= -0.1) declined.push(label);
    };
    addSignal("mention", kpiTrends.mention_rate);
    addSignal("citation", kpiTrends.citation_rate);
    addSignal("attribution", kpiTrends.attribution_accuracy);
    addSignal("composite index", kpiTrends.composite_index);
    addSignal("hallucination control", kpiTrends.hallucinations);

    if (improved.length === 0 && declined.length === 0) {
      return {
        summary: "Performance is stable versus the prior completed evaluation.",
        tone: "neutral" as const,
      };
    }
    if (declined.length === 0) {
      return {
        summary: `Improvement vs prior run in ${improved.join(", ")}.`,
        tone: "positive" as const,
      };
    }
    if (improved.length === 0) {
      return {
        summary: `Downward movement vs prior run in ${declined.join(", ")}.`,
        tone: "warning" as const,
      };
    }
    return {
      summary: `Improvement in ${improved.join(", ")}; watch ${declined.join(", ")}.`,
      tone: "mixed" as const,
    };
  }, [kpiTrends]);

  const executiveHeadline = useMemo(() => {
    const total = domainRows.length;
    if (total === 0) {
      return {
        title: "No monitored domains yet.",
        subtitle: "Add domains to start tracking visibility quality and improvement opportunities.",
      };
    }
    if (failedCount > 0) {
      return {
        title: `${plural(failedCount, "domain needs", "domains need")} attention to improve reliability.`,
        subtitle: `Top performer: ${best?.domain ?? "--"} | Priority opportunity: ${weakest?.domain ?? "--"}`,
      };
    }
    if (runningCount > 0) {
      return {
        title: `${plural(runningCount, "domain is", "domains are")} currently in progress.`,
        subtitle: `Latest completed evaluation: ${formatDateTime(latestCompletedRun)}`,
      };
    }
    if (strongCount === total) {
      return {
        title: "Visibility quality is strong across all monitored domains.",
        subtitle: `Top performer: ${best?.domain ?? "--"}`,
      };
    }
    return {
      title: `${strongCount} of ${total} monitored domains are performing strongly.`,
      subtitle: `Top performer: ${best?.domain ?? "--"} | Priority opportunity: ${weakest?.domain ?? "--"}`,
    };
  }, [best?.domain, domainRows.length, failedCount, latestCompletedRun, runningCount, strongCount, weakest?.domain]);

  if (loading) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Overview</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {KPI_ITEMS.map((_, i) => (
            <KpiCardSkeleton key={i} />
          ))}
        </div>
        <div className="mt-6 h-28 animate-pulse rounded-xl border border-gray-200 bg-gray-50/60" />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Overview</h1>
        <div className="card rounded-xl border-rose-200 bg-rose-50/50 p-4">
          <p className="text-rose-700" role="alert">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Overview</h1>
        <div className="card rounded-xl border-dashed border-gray-300 bg-gray-50/50 p-12 text-center">
          <p className="text-lg text-gray-700">No completed evaluation available yet.</p>
          <p className="mt-1 text-sm text-gray-500">Run your first evaluation to unlock portfolio performance insights for client reporting.</p>
        </div>
      </div>
    );
  }

  const { kpis } = data;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Overview</h1>
          <p className="mt-1 text-sm text-gray-500">Executive view of visibility quality, opportunity, and trend across monitored domains.</p>
        </div>
        {lastRefreshedAt != null && (
          <p className="rounded-md bg-gray-50 px-2 py-1 text-xs text-gray-500">Updated {new Date(lastRefreshedAt).toLocaleTimeString()}</p>
        )}
      </div>

      <section className="card mb-6 border border-gray-200 bg-white p-5">
        <h2 className="text-xl font-semibold text-gray-900">{executiveHeadline.title}</h2>
        <p className="mt-1 text-sm text-gray-600">{executiveHeadline.subtitle}</p>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {KPI_ITEMS.map(({ key, label, format, accent }) => (
          <KpiCard
            key={key}
            label={label}
            value={kpis[key]}
            format={format}
            accent={accent}
            trend={kpiTrends[key] ?? null}
          />
        ))}
      </div>

      <section className="mt-6">
        <h2 className="mb-1 text-lg font-semibold text-gray-900">Portfolio Signals</h2>
        <p className="mb-3 text-sm text-gray-500">Commercial interpretation of current monitoring coverage, momentum, and risk.</p>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-gray-500">Monitoring coverage</p>
            <p className="mt-1 text-sm font-medium text-gray-900">
              {doneCount} of {domainRows.length} domains completed
            </p>
            <p className="mt-1 text-xs text-gray-600">
              {runningCount} in progress, {failedCount} requiring attention.
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-gray-500">Improvement summary</p>
            <p
              className={`mt-1 text-sm font-medium ${
                improvementHighlights.tone === "positive"
                  ? "text-emerald-700"
                  : improvementHighlights.tone === "warning"
                    ? "text-rose-700"
                    : improvementHighlights.tone === "mixed"
                      ? "text-amber-700"
                      : "text-gray-900"
              }`}
            >
              {improvementHighlights.summary}
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-gray-500">Opportunity summary</p>
            <p className="mt-1 text-sm font-medium text-gray-900">
              Lowest citation: {lowestCitation?.domain ?? "--"}
            </p>
            <p className="mt-1 text-xs text-gray-600">
              {plural(lowAttributionCount, "domain has", "domains have")} low attribution (&lt;70%).
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-gray-500">Performance tiering</p>
            <p className="mt-1 text-sm font-medium text-gray-900">
              {highPerformingCount} high-performing, {stableCount} stable
            </p>
            <p className="mt-1 text-xs text-gray-600">
              {plural(atRiskCount, "domain is", "domains are")} currently at risk.
            </p>
          </div>
        </div>
      </section>

      <div className="mt-7">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-gray-900">Executive Snapshot</h2>
          {tenantId && (
            <Link
              href={`/tenants/${encodeURIComponent(tenantId)}/domains`}
              className="text-sm font-medium text-primary hover:underline"
            >
              Open domain performance {"->"}
            </Link>
          )}
        </div>
        {domainsLoading ? (
          <div className="card p-6">
            <p className="text-sm text-gray-500">Loading domain status...</p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-gray-500">Latest evaluation completed</p>
              <p className="mt-1 text-sm font-semibold text-gray-900">{formatDateTime(latestCompletedRun)}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-gray-500">Domains monitored</p>
              <p className="mt-1 text-lg font-semibold text-gray-900">{domainRows.length}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-gray-500">Completed / In progress / Needs attention</p>
              <p className="mt-1 text-sm font-semibold text-gray-900">
                <span className="text-emerald-700">{doneCount}</span>
                <span className="text-gray-400"> / </span>
                <span className="text-blue-700">{runningCount}</span>
                <span className="text-gray-400"> / </span>
                <span className="text-rose-700">{failedCount}</span>
              </p>
            </div>
            <div className="rounded-lg border border-emerald-300 bg-emerald-50/50 p-3 shadow-sm">
              <p className="flex items-center gap-1 text-xs uppercase tracking-wide text-emerald-700">
                <Trophy className="h-3.5 w-3.5" />
                Top performer
              </p>
              <p className="mt-1 text-sm font-semibold text-emerald-900">{best?.domain ?? "--"}</p>
              {best?.latest_rates && (
                <p className="text-xs font-medium text-emerald-800">
                  Attribution {(best.latest_rates.attribution_rate * 100).toFixed(1)}%
                </p>
              )}
            </div>
            <div className="rounded-lg border border-amber-300 bg-amber-50/50 p-3 shadow-sm">
              <p className="flex items-center gap-1 text-xs uppercase tracking-wide text-amber-700">
                <AlertTriangle className="h-3.5 w-3.5" />
                Priority opportunity
              </p>
              <p className="mt-1 text-sm font-semibold text-amber-900">
                {best && weakest && best.domain === weakest.domain ? "Same as top (single domain)" : weakest?.domain ?? "--"}
              </p>
              {weakest?.latest_rates && best !== weakest && (
                <p className="text-xs font-medium text-amber-800">
                  Attribution {(weakest.latest_rates.attribution_rate * 100).toFixed(1)}%
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="mt-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Domain Performance Overview</h2>
            <p className="text-sm text-gray-500">Scan strongest domains, at-risk domains, and where to focus next.</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Clock3 className="h-3.5 w-3.5" />
            Latest completed run: {formatDateTime(latestCompletedRun)}
          </div>
        </div>
        {!domainsLoading && (
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-md bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800">Top</span>
            <span className="rounded-md bg-rose-100 px-2 py-0.5 font-medium text-rose-800">Needs focus</span>
            <span className="text-gray-500">Tags indicate strongest and weakest current domain performance bands.</span>
          </div>
        )}
        {!domainsLoading && domainRows.length > 0 && (
          <div className="mb-3 rounded-lg border border-gray-200 bg-gray-50/70 px-4 py-3 text-sm text-gray-700">
            <span className="font-medium text-gray-900">How to read this: </span>
            Use the table below to see per-domain metrics. Domains tagged &quot;Needs focus&quot; or with low attribution are the best candidates for improvement.
          </div>
        )}

        {domainsLoading ? (
          <div className="card flex items-center justify-center p-8">
            <p className="text-gray-500">Loading domain results...</p>
          </div>
        ) : domainRows.length === 0 ? (
          <div className="card rounded-xl border-dashed border-gray-300 bg-gray-50/50 p-8 text-center">
            <BarChart3 className="mx-auto h-10 w-10 text-gray-400" />
            <p className="mt-2 text-gray-600">No monitored domains yet.</p>
            <p className="mt-1 text-sm text-gray-500">Add domains and run evaluation to unlock domain-level performance insights.</p>
          </div>
        ) : (
          <div className="card overflow-hidden border border-gray-200">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead>
                  <tr className="sticky top-0 z-10 border-b border-gray-200 bg-gray-50/95">
                    <th className="px-4 py-3 font-medium text-gray-700">Domain</th>
                    <th className="px-4 py-3 font-medium text-gray-700">Status</th>
                    <th className="px-4 py-3 font-medium text-gray-700">Mention</th>
                    <th className="px-4 py-3 font-medium text-gray-700">Citation</th>
                    <th className="px-4 py-3 font-medium text-gray-700">Attribution</th>
                    <th className="px-4 py-3 font-medium text-gray-700">Hallucination</th>
                    <th className="px-4 py-3 font-medium text-gray-700">Last evaluated</th>
                  </tr>
                </thead>
                <tbody>
                  {domainRows.map((row) => {
                    const rates = row.latest_rates;
                    const isStrong =
                      row.resolvedStatus === "DONE" &&
                      !!rates &&
                      rates.attribution_rate >= 0.9 &&
                      rates.hallucination_rate <= 0.01;
                    const isWeak =
                      row.resolvedStatus === "DONE" &&
                      !!rates &&
                      (rates.attribution_rate < 0.7 || rates.hallucination_rate > 0.05);

                    return (
                      <tr
                        key={row.domain}
                        className={`border-b border-gray-100 last:border-0 ${
                          isStrong
                            ? "bg-emerald-50/35 hover:bg-emerald-50/50"
                            : isWeak
                              ? "bg-rose-50/35 hover:bg-rose-50/50"
                              : "hover:bg-gray-50/50"
                        }`}
                      >
                        <td className="px-4 py-3 font-medium text-gray-900">
                          <div className="flex items-center gap-2">
                            <Globe2 className="h-4 w-4 text-gray-400" />
                            <span>{row.domain}</span>
                            {isStrong && (
                              <span className="inline-flex items-center rounded-md bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800">
                                Top
                              </span>
                            )}
                            {isWeak && (
                              <span className="inline-flex items-center rounded-md bg-rose-100 px-2 py-0.5 text-[11px] font-medium text-rose-800">
                                Needs focus
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${resolvedStatusBadgeClass(
                              row.resolvedStatus
                            )}`}
                          >
                            {statusLabel(row.resolvedStatus)}
                          </span>
                        </td>
                        {rates ? (
                          <>
                            <td className="px-4 py-3">
                              <MetricBadge type="mention" value={rates.mention_rate} />
                            </td>
                            <td className="px-4 py-3">
                              <MetricBadge type="citation" value={rates.citation_rate} />
                            </td>
                            <td className="px-4 py-3">
                              <MetricBadge type="attribution" value={rates.attribution_rate} />
                            </td>
                            <td className="px-4 py-3">
                              <MetricBadge type="hallucination" value={rates.hallucination_rate} />
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="px-4 py-3 text-gray-400">--</td>
                            <td className="px-4 py-3 text-gray-400">--</td>
                            <td className="px-4 py-3 text-gray-400">--</td>
                            <td className="px-4 py-3 text-gray-400">--</td>
                          </>
                        )}
                        <td className="px-4 py-3 text-gray-600">{formatDateTime(row.last_run_created_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
