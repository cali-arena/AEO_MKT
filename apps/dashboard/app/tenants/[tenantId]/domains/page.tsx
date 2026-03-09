"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { motion } from "framer-motion";

import { DomainDrawer } from "@/components/domains/DomainDrawer";
import { MetricBadge } from "@/components/ui/MetricBadge";
import { apiFetch, ApiError } from "@/lib/api";
import { resolveDomainStatus, resolvedStatusBadgeClass } from "@/lib/domainStatus";
import type {
  DomainJobStatusResponse,
  DomainListItem,
  DomainsCreateResponse,
  DomainsEvaluateResponse,
  DomainsListResponse,
  EvalMetricsRates,
} from "@/lib/types";

type SortKey = keyof EvalMetricsRates | "domain" | "status" | "actions";

function statusDetailsTooltip(row: DomainListItem): string {
  const parts: string[] = [];
  if (row.index_status) parts.push(`Index: ${row.index_status}`);
  if (row.last_indexed_at) parts.push(`Last indexed: ${new Date(row.last_indexed_at).toLocaleString()}`);
  if (row.eval_status) parts.push(`Eval: ${row.eval_status}`);
  if (row.last_run_created_at) parts.push(`Last eval: ${new Date(row.last_run_created_at).toLocaleString()}`);
  if (row.index_error) parts.push(`Index error: ${row.index_error}`);
  if (row.failure_reason) parts.push(`Eval error: ${row.failure_reason}`);
  return parts.join("\n");
}

const DOMAIN_REGEX =
  /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/i;

function normalizeDomain(raw: string): string | null {
  const candidate = raw
    .trim()
    .toLowerCase()
    .replace(/\\/g, "/")
    .replace(/^[a-z][a-z0-9+.-]*:\/\//i, "")
    .split("/")[0]
    .split("?")[0]
    .split("#")[0]
    .split("@")
    .pop()
    ?.split(":")[0]
    .replace(/^\.+|\.+$/g, "");
  if (!candidate || !DOMAIN_REGEX.test(candidate)) return null;
  return candidate;
}

const BLOCKED_PREFIXES = ["quote.", "app.", "secure.", "form."];

function isBlockedDomain(domain: string): boolean {
  const d = domain.trim().toLowerCase();
  return BLOCKED_PREFIXES.some((prefix) => d.startsWith(prefix));
}

function filterBlockedDomains(domains: string[]): { allowed: string[]; blocked: string[] } {
  const allowed: string[] = [];
  const blocked: string[] = [];
  for (const d of domains) {
    if (isBlockedDomain(d)) blocked.push(d);
    else allowed.push(d);
  }
  return { allowed, blocked };
}

function parseDomains(input: string): { valid: string[]; invalid: string[] } {
  const seen = new Set<string>();
  const valid: string[] = [];
  const invalid: string[] = [];
  for (const token of input.split(/[\n,;]+/)) {
    const trimmed = token.trim();
    if (!trimmed) continue;
    const normalized = normalizeDomain(trimmed);
    if (!normalized) {
      invalid.push(trimmed);
      continue;
    }
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    valid.push(normalized);
  }
  return { valid, invalid };
}

function domainsPath(tenantId: string): string {
  return `/tenants/${encodeURIComponent(tenantId)}/domains`;
}

function jobPath(tenantId: string, jobId: string): string {
  return `/tenants/${encodeURIComponent(tenantId)}/jobs/${encodeURIComponent(jobId)}`;
}

async function loadDomains(tenantId: string): Promise<DomainsListResponse> {
  const res = await apiFetch<DomainsListResponse>(domainsPath(tenantId), { tenantId });
  return {
    ...res,
    domains: (res.domains ?? []).map((row) => {
      const raw = String((row as { status?: string }).status ?? "pending").toLowerCase();
      const status = raw === "done" || raw === "failed" || raw === "running" ? raw : "pending";
      return { ...row, status };
    }),
  };
}

export default function DomainsPage() {
  const params = useParams();
  const tenantId = params?.tenantId as string | undefined;

  const [data, setData] = useState<DomainsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const [runMessage, setRunMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [domainInput, setDomainInput] = useState("");
  const [evalScope, setEvalScope] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("domain");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [drawerDomain, setDrawerDomain] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [bulkProgress, setBulkProgress] = useState<{ done: number; total: number } | null>(null);
  const [clearHistoryLoading, setClearHistoryLoading] = useState(false);
  const [deleteConfirmDomain, setDeleteConfirmDomain] = useState<string | null>(null);
  const [deletingDomain, setDeletingDomain] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null);
  const hasInFlightRows = useMemo(
    () =>
      (data?.domains ?? []).some((row) => {
        const resolved = resolveDomainStatus(row);
        return resolved !== "DONE" && resolved !== "FAILED";
      }),
    [data?.domains]
  );

  const refresh = useCallback(() => {
    if (!tenantId) return Promise.resolve();
    return loadDomains(tenantId)
      .then((res) => {
        setData(res);
        setError(null);
        setLastFetchedAt(Date.now());
      })
      .catch((err) => {
        const msg =
          err instanceof ApiError && err.status === 401
            ? "Missing auth header. Log in or set Authorization: Bearer tenant:<id>."
            : err instanceof Error
              ? err.message
              : "Failed to load domains";
        setError(msg);
      });
  }, [tenantId]);

  useEffect(() => {
    if (!tenantId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    loadDomains(tenantId)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setLastFetchedAt(Date.now());
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load domains");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  useEffect(() => {
    if (!tenantId || !activeJobId) return;
    let stopped = false;
    const poll = async () => {
      try {
        const job = await apiFetch<DomainJobStatusResponse>(jobPath(tenantId, activeJobId), { tenantId });
        if (stopped) return;
        setBulkProgress({ done: job.completed, total: job.total });
        if (job.status === "done") {
          setRunMessage({ type: "success", text: "Evaluation completed. Table is up to date." });
          setBulkProgress(null);
          setActiveJobId(null);
          await refresh();
        } else if (job.status === "failed") {
          setRunMessage({ type: "error", text: job.error_message || "Evaluation failed" });
          setBulkProgress(null);
          setActiveJobId(null);
          await refresh();
        } else {
          await refresh();
        }
      } catch (err) {
        if (!stopped) {
          const is404 = err instanceof ApiError && err.status === 404;
          if (is404) {
            setRunMessage({
              type: "error",
              text: "Job no longer found (server may have restarted). Refresh the page.",
            });
          } else {
            setRunMessage({
              type: "error",
              text: err instanceof Error ? err.message : "Failed to poll evaluation job",
            });
          }
          setBulkProgress(null);
          setActiveJobId(null);
        }
      }
    };
    poll();
    const interval = window.setInterval(poll, 2500);
    return () => {
      stopped = true;
      window.clearInterval(interval);
    };
  }, [tenantId, activeJobId, refresh]);

  useEffect(() => {
    if (!tenantId || !hasInFlightRows) return;
    let stopped = false;
    const poll = async () => {
      if (stopped) return;
      await refresh();
    };
    const interval = window.setInterval(poll, 3000);
    return () => {
      stopped = true;
      window.clearInterval(interval);
    };
  }, [tenantId, hasInFlightRows, refresh]);

  const startEvaluation = useCallback(
    async (domains: string[], successMessage: string) => {
      if (!tenantId) return;
      const payload = { domains };
      const res = await apiFetch<DomainsEvaluateResponse>(`${domainsPath(tenantId)}/evaluate`, {
        method: "POST",
        body: JSON.stringify(payload),
        tenantId,
      });
      setRunMessage({ type: "success", text: res.message || successMessage });
      setActiveJobId(res.orchestration_job_id ?? res.eval_job_id ?? res.job_id ?? null);
      await refresh();
    },
    [tenantId, refresh]
  );

  const resetTable = useCallback(() => {
    if (!tenantId) return;
    setRunMessage(null);
    setData(null);
    setError(null);
    setLoading(true);
    apiFetch<{ status: string; removed: number; message: string }>(
      `${domainsPath(tenantId)}?invalid_only=true`,
      { method: "DELETE", tenantId }
    )
      .then(() => loadDomains(tenantId))
      .then((res) => {
        setData(res);
        setError(null);
        setLastFetchedAt(Date.now());
      })
      .catch((err) => {
        const msg =
          err instanceof ApiError && err.status === 401
            ? "Missing auth header. Log in or set Authorization: Bearer tenant:<id>."
            : err instanceof Error
              ? err.message
              : "Failed to load domains";
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, [tenantId]);

  const adminKey = typeof process !== "undefined" ? process.env.NEXT_PUBLIC_ADMIN_KEY : undefined;
  const clearHistory = useCallback(async () => {
    if (!tenantId || !adminKey) return;
    setClearHistoryLoading(true);
    setRunMessage(null);
    try {
      const res = await apiFetch<{ status: string; message: string; deleted_eval_jobs: number; deleted_ingest_jobs: number }>(
        `${domainsPath(tenantId)}/clear-history`,
        {
          method: "POST",
          tenantId,
          headers: { "X-Admin-Key": adminKey },
        }
      );
      setRunMessage({ type: "success", text: res.message ?? "History cleared. Table refreshed." });
      await refresh();
    } catch (err) {
      const msg =
        err instanceof ApiError && err.status === 403
          ? "Admin only: set ADMIN_SECRET on server and NEXT_PUBLIC_ADMIN_KEY in dashboard."
          : err instanceof Error
            ? err.message
            : "Failed to clear history";
      setRunMessage({ type: "error", text: msg });
    } finally {
      setClearHistoryLoading(false);
    }
  }, [tenantId, adminKey, refresh]);

  const showToast = useCallback((type: "success" | "error", text: string) => {
    setToast({ type, text });
    const t = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(t);
  }, []);

  const deleteDomain = useCallback(
    async (domain: string) => {
      if (!tenantId) return;
      setDeletingDomain(domain);
      setDeleteConfirmDomain(null);
      try {
        await apiFetch<{ ok: boolean; deleted_domain: string }>(
          `${domainsPath(tenantId)}/${encodeURIComponent(domain)}/delete`,
          { method: "POST", tenantId }
        );
        showToast("success", "Domain removed");
        await refresh();
      } catch (err) {
        const msg =
          err instanceof ApiError && err.body && typeof err.body === "object" && "detail" in err.body
            ? String((err.body as { detail: unknown }).detail)
            : err instanceof Error
              ? err.message
              : "Failed to delete domain";
        showToast("error", msg);
      } finally {
        setDeletingDomain(null);
      }
    },
    [tenantId, refresh, showToast]
  );

  const evaluateDomains = useCallback(async () => {
    if (!tenantId) return;
    const { valid, invalid } = parseDomains(domainInput);
    if (valid.length === 0) {
      setRunMessage({
        type: "error",
        text: invalid.length > 0 ? `Invalid domain(s): ${invalid.join(", ")}` : "Enter at least one domain",
      });
      return;
    }
    const { allowed, blocked } = filterBlockedDomains(valid);
    if (allowed.length === 0) {
      setRunMessage({
        type: "error",
        text:
          blocked.length > 0
            ? "Quote or form subdomains cannot be evaluated. Please use the main domain."
            : "Enter at least one domain",
      });
      return;
    }
    setRunLoading(true);
    setRunMessage(null);
    try {
      await apiFetch<DomainsCreateResponse>(domainsPath(tenantId), {
        method: "POST",
        body: JSON.stringify({ domains: allowed }),
        tenantId,
      });
      await refresh();
      await startEvaluation(
        allowed,
        `Added ${allowed.length} domain(s). Evaluation is running and the table will update automatically.`
      );
      setDomainInput("");
      if (invalid.length > 0) {
        setRunMessage({
          type: "success",
          text: `Added ${allowed.length} domain(s). Ignored invalid entries: ${invalid.join(", ")}.`,
        });
      } else if (blocked.length > 0) {
        setRunMessage({
          type: "success",
          text: `Added ${allowed.length} domain(s). Quote/form subdomains were skipped—use the main domain.`,
        });
      }
    } catch (err) {
      setRunMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to add and evaluate domains",
      });
      await refresh();
      setBulkProgress(null);
    } finally {
      setRunLoading(false);
    }
  }, [tenantId, domainInput, refresh, startEvaluation]);

  const runEval = useCallback(
    async (domain: string | null) => {
      if (!tenantId) return;
      const domainsToEval = domain
        ? [domain]
        : (data?.domains ?? []).map((d) => d.domain);
      if (domainsToEval.length === 0) {
        setRunMessage({
          type: "error",
          text: domain ? "Domain not in list." : "No monitored domains. Add domains first.",
        });
        return;
      }
      setRunLoading(true);
      setRunMessage(null);
      try {
        await startEvaluation(
          domainsToEval,
          domain
            ? `Evaluation started for ${domain}.`
            : "Evaluation started for all monitored domains."
        );
        await refresh();
      } catch (err) {
        setRunMessage({
          type: "error",
          text: err instanceof Error ? err.message : "Failed to start evaluation",
        });
      } finally {
        setRunLoading(false);
      }
    },
    [tenantId, data?.domains, refresh, startEvaluation]
  );

  const domainsSorted = useMemo(() => {
    const rows = [...(data?.domains ?? [])];
    const metricKeys: (keyof EvalMetricsRates)[] = [
      "mention_rate",
      "citation_rate",
      "attribution_rate",
      "hallucination_rate",
    ];
    return rows.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "domain") {
        cmp = a.domain.localeCompare(b.domain);
      } else if (sortKey === "status" || sortKey === "actions") {
        const sa = resolveDomainStatus(a);
        const sb = resolveDomainStatus(b);
        cmp = sa.localeCompare(sb);
      } else if (metricKeys.includes(sortKey)) {
        const left = a.latest_rates?.[sortKey] ?? -1;
        const right = b.latest_rates?.[sortKey] ?? -1;
        cmp = left - right;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data?.domains, sortDir, sortKey]);

  const toggleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
        return;
      }
      setSortKey(key);
      setSortDir("asc");
    },
    [sortKey]
  );

  const drawerRates = useMemo(() => {
    if (!drawerDomain) return null;
    return data?.domains.find((d) => d.domain === drawerDomain)?.latest_rates ?? null;
  }, [data?.domains, drawerDomain]);

  if (!tenantId || loading) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Domains</h1>
        <div className="animate-pulse overflow-hidden rounded-lg border border-gray-200">
          <table className="min-w-full">
            <thead className="bg-gray-50">
              <tr>
                {["Domain", "Mention", "Citation", "Attribution", "Hallucination"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left">
                    <div className="h-4 w-20 rounded bg-gray-200" />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {[1, 2, 3].map((i) => (
                <tr key={i}>
                  <td className="px-4 py-3">
                    <div className="h-4 w-24 rounded bg-gray-200" />
                  </td>
                  {[1, 2, 3, 4].map((j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 w-12 rounded bg-gray-200" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  const basePath = `/tenants/${encodeURIComponent(tenantId)}`;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <h1 className="text-2xl font-semibold text-gray-900">Domains</h1>
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="eval-domain" className="sr-only">
            Evaluate scope
          </label>
          <select
            id="eval-domain"
            className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm"
            value={evalScope}
            onChange={(e) => setEvalScope(e.target.value)}
            disabled={runLoading}
          >
            <option value="">All domains</option>
            {domainsSorted.map((row) => (
              <option key={row.domain} value={row.domain}>
                {row.domain}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => runEval(evalScope || null)}
            disabled={runLoading}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {runLoading ? "Starting..." : "Run evaluation"}
          </button>
        </div>
        {runMessage && (
          <span className={`text-sm ${runMessage.type === "error" ? "text-red-600" : "text-green-700"}`}>
            {runMessage.text}
          </span>
        )}
      </div>

      {error && (
        <p className="mb-4 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <div id="add-domains-section" className="mb-4 card rounded-xl border-gray-200 bg-gray-50/80 p-4">
        <p className="mb-2 text-sm font-medium text-gray-700">Add domain(s) to evaluate</p>
        <p className="mb-3 text-xs text-gray-500">
          Paste one or more domains (newline/comma/semicolon). Domains are created on the server; the table refetches
          and then evaluation runs. Quote/form subdomains (quote., app., secure., form.) cannot be evaluated—use the main domain.
        </p>
        <div className="flex flex-col gap-2">
          <textarea
            placeholder="e.g. coasttocoastmovers.com or many domains"
            value={domainInput}
            onChange={(e) => setDomainInput(e.target.value)}
            rows={5}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400"
            id="add-domain-input"
            disabled={runLoading}
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={evaluateDomains}
              disabled={runLoading || !domainInput.trim()}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              {activeJobId && bulkProgress
                ? `Running ${bulkProgress.done} of ${bulkProgress.total}...`
                : runLoading
                  ? "Starting..."
                  : "Evaluate domain(s)"}
            </button>
            {bulkProgress && (
              <span className="text-xs text-gray-500">
                {bulkProgress.done} of {bulkProgress.total}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-xs text-gray-500">Eval runs automatically. Click a done row for details.</p>
          <span className="rounded-md bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
            {domainsSorted.length} domain{domainsSorted.length !== 1 ? "s" : ""} monitored
          </span>
          {lastFetchedAt != null && (
            <span className="text-xs text-gray-400" title="Table data last refreshed">
              Last updated {new Date(lastFetchedAt).toLocaleTimeString()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => document.getElementById("add-domains-section")?.scrollIntoView({ behavior: "smooth" })}
            className="shrink-0 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90"
          >
            Add more domains
          </button>
          <button
            type="button"
            onClick={() => refresh()}
            disabled={loading}
            className="shrink-0 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Refresh table
          </button>
          <button
            type="button"
            onClick={() => resetTable()}
            disabled={loading}
            className="shrink-0 rounded-md border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
            title="Clear client cache and refetch domains from server"
          >
            Reset table
          </button>
          {adminKey && (
            <button
              type="button"
              onClick={() => clearHistory()}
              disabled={clearHistoryLoading || loading}
              className="shrink-0 rounded-md border border-rose-300 bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-800 hover:bg-rose-100 disabled:opacity-50"
              title="Admin only: delete all domain eval and ingest job rows for this tenant"
            >
              {clearHistoryLoading ? "Clearing..." : "Clear history"}
            </button>
          )}
        </div>
      </div>

      <div className="card max-h-[min(70vh,600px)] overflow-auto">
        <table className="min-w-full">
          <thead className="sticky top-0 z-10 bg-gray-50/95 shadow-sm backdrop-blur dark:bg-slate-800/95">
            <tr>
              {[
                { key: "domain" as const, label: "Domain" },
                { key: "status" as const, label: "Status" },
                { key: "mention_rate" as const, label: "Mention" },
                { key: "citation_rate" as const, label: "Citation" },
                { key: "attribution_rate" as const, label: "Attribution" },
                { key: "hallucination_rate" as const, label: "Hallucination" },
                { key: "actions" as const, label: "" },
              ].map(({ key, label }) => (
                <th key={key} className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  {key === "status" || key === "actions" ? (
                    label
                  ) : (
                    <button type="button" onClick={() => toggleSort(key)} className="flex items-center gap-1 hover:text-gray-900">
                      {label}
                      {sortKey === key ? (
                        sortDir === "asc" ? <ArrowUp className="h-3.5 w-3.5" /> : <ArrowDown className="h-3.5 w-3.5" />
                      ) : (
                        <ArrowUpDown className="h-3.5 w-3.5 opacity-50" />
                      )}
                    </button>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {domainsSorted.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-sm text-gray-500">
                  No monitored domains yet.
                </td>
              </tr>
            )}
            {domainsSorted.map((row) => {
              const rates = row.latest_rates;
              const resolvedStatus = resolveDomainStatus(row);
              const isCompleted = resolvedStatus === "DONE";
              const isIndexFailed = resolvedStatus === "FAILED" || (row.index_status ?? "").toUpperCase() === "FAILED";
              const isEvalFailed = row.status === "failed";
              const showRetry = isIndexFailed || isEvalFailed;
              const tooltip = statusDetailsTooltip(row);
              return (
                <motion.tr
                  key={row.domain}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.2 }}
                  onClick={() => {
                    if (isCompleted) setDrawerDomain(row.domain);
                  }}
                  className={`transition-colors ${
                    isCompleted
                      ? "cursor-pointer hover:bg-primary/5"
                      : "bg-primary/5"
                  }`}
                >
                  <td className="px-3 py-2 font-medium text-primary">{row.domain}</td>
                  <td className="px-3 py-2" title={tooltip || undefined}>
                    <div className="flex flex-col gap-0.5">
                      <span
                        className={`inline-flex w-fit rounded-md px-2 py-0.5 text-xs font-medium ${resolvedStatusBadgeClass(resolvedStatus)}`}
                      >
                        {resolvedStatus}
                      </span>
                      {(row.index_status || row.last_indexed_at) && (
                        <span className="text-xs text-gray-500">
                          {[row.index_status, row.last_indexed_at ? new Date(row.last_indexed_at).toLocaleString() : null]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      )}
                      {row.eval_status && row.eval_status !== "NONE" && (
                        <span className="text-xs text-gray-500">
                          Eval {row.eval_status}
                          {row.last_run_created_at ? ` · ${new Date(row.last_run_created_at).toLocaleString()}` : ""}
                        </span>
                      )}
                      {(row.index_error || row.failure_reason) && (
                        <span className="max-w-[200px] truncate text-xs text-rose-600" title={row.index_error ?? row.failure_reason ?? ""}>
                          {row.index_error ?? row.failure_reason}
                        </span>
                      )}
                    </div>
                  </td>
                  {isCompleted && rates ? (
                    <>
                      <td className="px-3 py-2">
                        <MetricBadge type="mention" value={rates.mention_rate} />
                      </td>
                      <td className="px-3 py-2">
                        <MetricBadge type="citation" value={rates.citation_rate} />
                      </td>
                      <td className="px-3 py-2">
                        <MetricBadge type="attribution" value={rates.attribution_rate} />
                      </td>
                      <td className="px-3 py-2">
                        <MetricBadge type="hallucination" value={rates.hallucination_rate} />
                      </td>
                    </>
                  ) : isCompleted ? (
                    <>
                      <td className="px-3 py-2">
                        <span className="inline-flex rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
                          Done
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">-</td>
                      <td className="px-3 py-2 text-xs text-gray-500">-</td>
                      <td className="px-3 py-2 text-xs text-gray-500">-</td>
                    </>
                  ) : (
                    <>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${
                            resolvedStatus === "FAILED"
                              ? "bg-rose-100 text-rose-800"
                              : resolvedStatus === "EVALUATING"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {resolvedStatus === "FAILED"
                            ? "Failed"
                            : resolvedStatus === "EVALUATING"
                              ? "Running..."
                              : "Pending"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">-</td>
                      <td className="px-3 py-2 text-xs text-gray-500">-</td>
                      <td className="px-3 py-2 text-xs text-gray-500">-</td>
                    </>
                  )}
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <div className="flex flex-wrap items-center gap-1">
                      {showRetry && (
                        <button
                          type="button"
                          onClick={() => runEval(row.domain)}
                          disabled={runLoading}
                          className="rounded-md border border-rose-300 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                        >
                          Retry
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setDeleteConfirmDomain(row.domain)}
                        disabled={deletingDomain !== null}
                        className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                      >
                        {deletingDomain === row.domain ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <DomainDrawer
        domain={drawerDomain}
        rates={drawerRates}
        basePath={basePath}
        onClose={() => setDrawerDomain(null)}
      />

      {deleteConfirmDomain && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-labelledby="delete-domain-title">
          <div className="mx-4 w-full max-w-sm rounded-lg bg-white p-4 shadow-xl">
            <h2 id="delete-domain-title" className="text-lg font-semibold text-gray-900">Remove domain?</h2>
            <p className="mt-2 text-sm text-gray-600">
              This will remove the domain and its indexed data. You can add it again later.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteConfirmDomain(null)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => deleteDomain(deleteConfirmDomain)}
                disabled={deletingDomain !== null}
                className="rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div
          className={`fixed bottom-4 right-4 z-50 rounded-lg px-4 py-2 text-sm font-medium shadow-lg ${
            toast.type === "success" ? "bg-emerald-600 text-white" : "bg-rose-600 text-white"
          }`}
          role="status"
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}
