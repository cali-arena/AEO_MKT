"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { motion } from "framer-motion";

import { DomainDrawer } from "@/components/domains/DomainDrawer";
import { MetricBadge } from "@/components/ui/MetricBadge";
import { apiFetch } from "@/lib/api";
import type {
  DomainJobStatusResponse,
  DomainsCreateResponse,
  DomainsEvaluateResponse,
  DomainsListResponse,
  EvalMetricsRates,
} from "@/lib/types";

type SortKey = keyof EvalMetricsRates | "domain";

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
  return apiFetch<DomainsListResponse>(domainsPath(tenantId), { tenantId });
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

  const refresh = useCallback(() => {
    if (!tenantId) return Promise.resolve();
    return loadDomains(tenantId)
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load domains");
      });
  }, [tenantId]);

  useEffect(() => {
    if (!tenantId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    loadDomains(tenantId)
      .then((res) => {
        if (!cancelled) setData(res);
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
        await refresh();
        setBulkProgress({ done: job.completed, total: job.total });
        if (job.status === "completed") {
          setRunMessage({ type: "success", text: "Evaluation completed. Table is up to date." });
          setBulkProgress(null);
          setActiveJobId(null);
        } else if (job.status === "failed") {
          setRunMessage({ type: "error", text: job.error || "Evaluation failed" });
          setBulkProgress(null);
          setActiveJobId(null);
        }
      } catch (err) {
        if (!stopped) {
          setRunMessage({
            type: "error",
            text: err instanceof Error ? err.message : "Failed to poll evaluation job",
          });
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

  const optimisticUpsertDomains = useCallback(
    (domains: string[]) => {
      if (!tenantId || domains.length === 0) return;
      setData((prev) => {
        const current: DomainsListResponse = prev ?? { tenant_id: tenantId, run_id: null, domains: [] };
        const map = new Map(current.domains.map((row) => [row.domain, row]));
        for (const domain of domains) {
          const existing = map.get(domain);
          map.set(domain, {
            domain,
            status: "running",
            latest_rates: existing?.latest_rates ?? null,
          });
        }
        return {
          ...current,
          domains: Array.from(map.values()),
        };
      });
    },
    [tenantId]
  );

  const startEvaluation = useCallback(
    async (domains: string[] | null, successMessage: string) => {
      if (!tenantId) return;
      const payload = domains ? { domains } : {};
      const res = await apiFetch<DomainsEvaluateResponse>(`${domainsPath(tenantId)}/evaluate`, {
        method: "POST",
        body: JSON.stringify(payload),
        tenantId,
      });
      setRunMessage({ type: "success", text: successMessage || res.message });
      setActiveJobId(res.job_id);
    },
    [tenantId]
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
    setRunLoading(true);
    setRunMessage(null);
    optimisticUpsertDomains(valid);
    try {
      await apiFetch<DomainsCreateResponse>(domainsPath(tenantId), {
        method: "POST",
        body: JSON.stringify({ domains: valid }),
        tenantId,
      });
      await startEvaluation(
        valid,
        `Added ${valid.length} domain(s). Evaluation is running and the table will update automatically.`
      );
      setDomainInput("");
      if (invalid.length > 0) {
        setRunMessage({
          type: "success",
          text: `Added ${valid.length} domain(s). Ignored invalid entries: ${invalid.join(", ")}.`,
        });
      }
      await refresh();
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
  }, [tenantId, domainInput, optimisticUpsertDomains, refresh, startEvaluation]);

  const runEval = useCallback(
    async (domain: string | null) => {
      if (!tenantId) return;
      setRunLoading(true);
      setRunMessage(null);
      if (domain) {
        optimisticUpsertDomains([domain]);
      }
      try {
        await startEvaluation(
          domain ? [domain] : null,
          domain
            ? `Evaluation started for ${domain}.`
            : "Evaluation started for all monitored domains."
        );
      } catch (err) {
        setRunMessage({
          type: "error",
          text: err instanceof Error ? err.message : "Failed to start evaluation",
        });
      } finally {
        setRunLoading(false);
      }
    },
    [tenantId, optimisticUpsertDomains, startEvaluation]
  );

  const domainsSorted = useMemo(() => {
    const rows = [...(data?.domains ?? [])];
    return rows.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "domain") {
        cmp = a.domain.localeCompare(b.domain);
      } else {
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
          Paste one or more domains (newline/comma/semicolon). New rows appear immediately as running and update
          automatically when evaluation completes.
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
          <p className="text-xs text-gray-500">Eval runs automatically. Click a completed row for details.</p>
          <span className="rounded-md bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
            {domainsSorted.length} domain{domainsSorted.length !== 1 ? "s" : ""} monitored
          </span>
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
        </div>
      </div>

      <div className="card max-h-[min(70vh,600px)] overflow-auto">
        <table className="min-w-full">
          <thead className="sticky top-0 z-10 bg-gray-50/95 shadow-sm backdrop-blur dark:bg-slate-800/95">
            <tr>
              {[
                { key: "domain" as const, label: "Domain" },
                { key: "mention_rate" as const, label: "Mention" },
                { key: "citation_rate" as const, label: "Citation" },
                { key: "attribution_rate" as const, label: "Attribution" },
                { key: "hallucination_rate" as const, label: "Hallucination" },
              ].map(({ key, label }) => (
                <th key={key} className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  <button type="button" onClick={() => toggleSort(key)} className="flex items-center gap-1 hover:text-gray-900">
                    {label}
                    {sortKey === key ? (
                      sortDir === "asc" ? <ArrowUp className="h-3.5 w-3.5" /> : <ArrowDown className="h-3.5 w-3.5" />
                    ) : (
                      <ArrowUpDown className="h-3.5 w-3.5 opacity-50" />
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {domainsSorted.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-sm text-gray-500">
                  No monitored domains yet.
                </td>
              </tr>
            )}
            {domainsSorted.map((row) => {
              const rates = row.latest_rates;
              const isCompleted = row.status === "completed" && rates !== null;
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
                  ) : (
                    <>
                      <td className="px-3 py-2">
                        <span className="inline-flex rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                          {row.status === "pending" ? "Pending" : "Running..."}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">-</td>
                      <td className="px-3 py-2 text-xs text-gray-500">-</td>
                      <td className="px-3 py-2 text-xs text-gray-500">-</td>
                    </>
                  )}
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
    </div>
  );
}
