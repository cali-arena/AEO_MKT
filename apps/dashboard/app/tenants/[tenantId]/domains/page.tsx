"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import type { EvalMetricsLatestOut, EvalMetricsRates } from "@/lib/types";
import { MetricBadge } from "@/components/ui/MetricBadge";
import { DomainDrawer } from "@/components/domains/DomainDrawer";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";

function loadData(_tenantId: string) {
  return apiFetch<EvalMetricsLatestOut>("/eval/metrics/latest");
}

export default function DomainsPage() {
  const params = useParams();
  const tenantId = params?.tenantId as string | undefined;
  const [data, setData] = useState<EvalMetricsLatestOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const [runMessage, setRunMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [evalScope, setEvalScope] = useState<string>("");
  const [domainInput, setDomainInput] = useState<string>("");
  const [sortKey, setSortKey] = useState<keyof EvalMetricsRates | "domain">("domain");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [drawerDomain, setDrawerDomain] = useState<string | null>(null);
  const [bulkDomains, setBulkDomains] = useState("");
  const [addingBulk, setAddingBulk] = useState(false);
  const [bulkProgress, setBulkProgress] = useState<{ done: number; total: number } | null>(null);

  const domainsSorted = useMemo(() => {
    const perDomain = data?.per_domain;
    if (!perDomain) return [];
    const entries = Object.entries(perDomain);
    return entries.sort(([nameA, ratesA], [nameB, ratesB]) => {
      let a: string | number, b: string | number;
      if (sortKey === "domain") {
        a = nameA;
        b = nameB;
      } else {
        a = ratesA[sortKey];
        b = ratesB[sortKey];
      }
      const cmp = typeof a === "string" ? a.localeCompare(b as string) : (a as number) - (b as number);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data?.per_domain, sortKey, sortDir]);

  const toggleSort = useCallback((key: keyof EvalMetricsRates | "domain") => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  }, [sortKey]);

  const refresh = useCallback(() => {
    if (!tenantId) return;
    setLoading(true);
    loadData(tenantId)
      .then(setData)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setData(null);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load domains");
        }
      })
      .finally(() => setLoading(false));
  }, [tenantId]);

  useEffect(() => {
    if (!tenantId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    loadData(tenantId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setData(null);
            setError(null);
          } else {
            setError(err instanceof Error ? err.message : "Failed to load domains");
          }
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  const runEval = useCallback(
    (domain: string | null) => {
      if (!tenantId) return;
      setRunLoading(true);
      setRunMessage(null);
      apiFetch<{ status: string; message: string }>("/eval/run", {
        method: "POST",
        body: JSON.stringify(domain ? { domain } : {}),
      })
        .then((res) => {
          setRunMessage({ type: "success", text: res.message });
          setTimeout(refresh, 2000);
        })
        .catch((err) => {
          setRunMessage({
            type: "error",
            text: err instanceof Error ? err.message : "Failed to start evaluation",
          });
        })
        .finally(() => setRunLoading(false));
    },
    [tenantId, refresh]
  );

  const addDomainAndRunEval = useCallback(
    (domain: string) => {
      if (!tenantId || !domain.trim()) return;
      setRunLoading(true);
      setRunMessage(null);
      apiFetch<{ status: string; message: string }>("/eval/domains", {
        method: "POST",
        body: JSON.stringify({ domain: domain.trim() }),
      })
        .then((res) => {
          setRunMessage({ type: "success", text: res.message });
          setDomainInput("");
          setTimeout(refresh, 2000);
        })
        .catch((err) => {
          setRunMessage({
            type: "error",
            text: err instanceof Error ? err.message : "Failed to add domain and start evaluation",
          });
        })
        .finally(() => setRunLoading(false));
    },
    [tenantId, refresh]
  );

  const addMultipleDomains = useCallback(async () => {
    const lines = bulkDomains
      .split(/[\n,;]+/)
      .map((d) => d.trim().toLowerCase())
      .filter((d) => d.length > 0);
    const unique = Array.from(new Set(lines));
    if (!tenantId || unique.length === 0) return;
    setAddingBulk(true);
    setBulkProgress({ done: 0, total: unique.length });
    setRunMessage(null);
    let lastError: string | null = null;
    for (let i = 0; i < unique.length; i++) {
      setBulkProgress({ done: i, total: unique.length });
      try {
        await apiFetch<{ status: string; message: string }>("/eval/domains", {
          method: "POST",
          body: JSON.stringify({ domain: unique[i] }),
        });
      } catch (err) {
        lastError = err instanceof Error ? err.message : "Failed to add domain";
      }
      if (i < unique.length - 1) await new Promise((r) => setTimeout(r, 400));
    }
    setBulkProgress({ done: unique.length, total: unique.length });
    setRunMessage(
      lastError
        ? { type: "error", text: `Added ${unique.length - 1}; last failed: ${lastError}` }
        : { type: "success", text: `Added ${unique.length} domain(s). Eval running 24/7. Refresh in a moment.` }
    );
    setBulkDomains("");
    setTimeout(() => {
      setAddingBulk(false);
      setBulkProgress(null);
      refresh();
    }, 1500);
  }, [tenantId, bulkDomains, refresh]);

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

  if (error) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Domains</h1>
        <p className="text-red-600" role="alert">{error}</p>
      </div>
    );
  }

  if (!data || Object.keys(data.per_domain).length === 0) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Domains</h1>
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <p className="text-gray-600">No domains yet.</p>
          <p className="mt-1 text-sm text-gray-500">Run an eval to see per-domain metrics.</p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
            <label htmlFor="domain-to-eval" className="text-sm text-gray-600">
              Domain to evaluate:
            </label>
            <input
              id="domain-to-eval"
              type="text"
              placeholder="e.g. example.com (optional — leave empty for all)"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              className="min-w-[200px] rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() =>
                domainInput.trim()
                  ? addDomainAndRunEval(domainInput.trim())
                  : runEval(null)
              }
              disabled={runLoading}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {runLoading ? "Starting…" : domainInput.trim() ? "Add domain and run evaluation" : "Run evaluation"}
            </button>
          </div>
          {runMessage && (
            <p className={`mt-3 text-sm ${runMessage.type === "error" ? "text-red-600" : "text-green-700"}`}>
              {runMessage.text}
            </p>
          )}
          <p className="mt-4 text-xs text-gray-400">Added domains are evaluated automatically 24/7 on the server.</p>
          {runMessage?.type === "error" && runMessage.text.toLowerCase().includes("not found") && (
            <p className="mt-2 text-xs text-amber-700">
              If you see &quot;Not Found&quot;, ensure the API on the VM has the latest code and NEXT_PUBLIC_API_BASE in Vercel points to your tunnel URL.
            </p>
          )}
        </div>
      </div>
    );
  }

  const basePath = `/tenants/${encodeURIComponent(tenantId!)}`;
  const drawerRates = data && drawerDomain ? data.per_domain[drawerDomain] ?? null : null;

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
            {domainsSorted.map(([d]) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => runEval(evalScope || null)}
            disabled={runLoading}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {runLoading ? "Starting…" : "Run evaluation"}
          </button>
        </div>
        {runMessage && (
          <span className={`text-sm ${runMessage.type === "error" ? "text-red-600" : "text-green-700"}`}>
            {runMessage.text}
          </span>
        )}
      </div>

      <div className="mb-4 card rounded-xl border-gray-200 bg-gray-50/80 p-4">
        <p className="mb-2 text-sm font-medium text-gray-700">Add domain(s) to evaluate</p>
        <p className="mb-3 text-xs text-gray-500">
          Add one domain in the field below, or paste multiple domains (one per line or comma/semicolon separated) and click &quot;Add all&quot;. Domains are saved and eval runs 24/7. Refresh after a moment to see them in the table.
        </p>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="e.g. coasttocoastmovers.com"
            value={domainInput}
            onChange={(e) => setDomainInput(e.target.value)}
            className="min-w-[220px] rounded border border-gray-300 px-3 py-2 text-sm"
            id="add-domain-input"
          />
          <button
            type="button"
            onClick={() => addDomainAndRunEval(domainInput.trim())}
            disabled={runLoading || addingBulk || !domainInput.trim()}
            className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            {runLoading ? "Starting…" : "Evaluate this domain"}
          </button>
        </div>
        <div className="flex flex-col gap-2">
          <textarea
            placeholder="Paste multiple domains (one per line or comma/semicolon separated)"
            value={bulkDomains}
            onChange={(e) => setBulkDomains(e.target.value)}
            rows={3}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400"
            disabled={addingBulk}
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={addMultipleDomains}
              disabled={addingBulk || !bulkDomains.trim()}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
            >
              {addingBulk && bulkProgress
                ? `Adding ${bulkProgress.done} of ${bulkProgress.total}…`
                : "Add all domains"}
            </button>
            {bulkProgress && (
              <span className="text-xs text-gray-500">
                {bulkProgress.done} of {bulkProgress.total} added
              </span>
            )}
          </div>
        </div>
      </div>

      <p className="mb-2 text-xs text-gray-500">Eval runs automatically 24/7 on the server. Click a row to open domain details.</p>
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
                  <button
                    type="button"
                    onClick={() => toggleSort(key)}
                    className="flex items-center gap-1 hover:text-gray-900"
                  >
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
            {domainsSorted.map(([domain, rates]) => (
              <tr
                key={domain}
                onClick={() => setDrawerDomain(domain)}
                className={`cursor-pointer transition-colors hover:bg-primary/5 ${
                  rates.hallucination_rate > 0 ? "bg-rose-50/50 hover:bg-rose-100/50" : ""
                }`}
              >
                <td className="px-3 py-2 font-medium text-primary">
                  {domain}
                </td>
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
              </tr>
            ))}
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
