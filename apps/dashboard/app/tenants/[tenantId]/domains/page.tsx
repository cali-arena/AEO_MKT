"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import type { EvalMetricsLatestOut } from "@/lib/types";

function loadData(tenantId: string) {
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

  if (!tenantId || loading) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Domains</h1>
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
              onClick={() => runEval(domainInput.trim() || null)}
              disabled={runLoading}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {runLoading ? "Starting…" : "Run evaluation"}
            </button>
          </div>
          {runMessage && (
            <p className={`mt-3 text-sm ${runMessage.type === "error" ? "text-red-600" : "text-green-700"}`}>
              {runMessage.text}
            </p>
          )}
          <p className="mt-4 text-xs text-gray-400">Eval also runs automatically 24/7 on the server.</p>
          {runMessage?.type === "error" && runMessage.text.toLowerCase().includes("not found") && (
            <p className="mt-2 text-xs text-amber-700">
              If you see &quot;Not Found&quot;, ensure the API on the VM has the latest code and NEXT_PUBLIC_API_BASE in Vercel points to your tunnel URL.
            </p>
          )}
        </div>
      </div>
    );
  }

  const domains = Object.entries(data.per_domain).sort(([a], [b]) => a.localeCompare(b));
  const basePath = `/tenants/${encodeURIComponent(tenantId)}`;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <h1 className="text-xl font-semibold">Domains</h1>
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
            {domains.map(([d]) => (
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
      <p className="mb-2 text-xs text-gray-500">Eval runs automatically 24/7 on the server. Use the button to run now.</p>
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Domain
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Mention
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Citation
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Attribution
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Hallucination
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {domains.map(([domain, rates]) => (
              <tr key={domain} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <Link
                    href={`${basePath}/worst-queries?domain=${encodeURIComponent(domain)}`}
                    className="font-medium text-blue-600 hover:text-blue-800 hover:underline"
                  >
                    {domain}
                  </Link>
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {(rates.mention_rate * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {(rates.citation_rate * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {(rates.attribution_rate * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-sm text-gray-900">
                  {(rates.hallucination_rate * 100).toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
