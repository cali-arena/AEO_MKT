"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import type { EvalRunsResponse, EvalRunResultsResponse, EvalResultRow } from "@/lib/types";

type SortKey = "query_text" | "refused" | "citation_ok" | "evidence_count" | "avg_confidence" | "top_cited_urls";
type SortDir = "asc" | "desc";

function formatUrls(val: Record<string, unknown> | unknown[] | null): string {
  if (val == null) return "—";
  if (Array.isArray(val)) return val.length > 0 ? `${val.length} cited` : "—";
  const obj = val as Record<string, unknown>;
  const keys = Object.keys(obj);
  return keys.length > 0 ? `${keys.length} cited` : "—";
}

export default function WorstQueriesPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const tenantId = params?.tenantId as string | undefined;

  const domainParam = searchParams.get("domain") ?? "";
  const failedOnlyParam = searchParams.get("failed_only");
  const refusedOnlyParam = searchParams.get("refused_only");

  const [domain, setDomain] = useState(domainParam);
  const [failedOnly, setFailedOnly] = useState(failedOnlyParam !== "false");
  const [refusedOnly, setRefusedOnly] = useState(refusedOnlyParam === "true");
  const [runId, setRunId] = useState<string | null>(null);
  const [results, setResults] = useState<EvalResultRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("query_text");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // Sync URL params to state on mount/change
  useEffect(() => {
    setDomain(domainParam);
    setFailedOnly(failedOnlyParam !== "false");
    setRefusedOnly(refusedOnlyParam === "true");
  }, [domainParam, failedOnlyParam, refusedOnlyParam]);

  useEffect(() => {
    if (!tenantId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiFetch<EvalRunsResponse>("/eval/runs?limit=1")
      .then((runsRes) => {
        if (cancelled) return;
        const run = runsRes.runs[0];
        if (!run) {
          setRunId(null);
          setResults([]);
          setLoading(false);
          return;
        }
        setRunId(run.run_id);
        const q = new URLSearchParams();
        if (domainParam) q.set("domain", domainParam);
        q.set("failed_only", String(failedOnlyParam !== "false"));
        q.set("refused_only", String(refusedOnlyParam === "true"));
        q.set("limit", "500");
        return apiFetch<EvalRunResultsResponse>(`/eval/runs/${run.run_id}/results?${q}`);
      })
      .then((resultsRes) => {
        if (cancelled || !resultsRes) return;
        setResults(resultsRes.results);
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setRunId(null);
            setResults([]);
            setError(null);
          } else {
            setError(err instanceof Error ? err.message : "Failed to load results");
          }
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [tenantId, domainParam, failedOnlyParam, refusedOnlyParam]);

  const handleSort = (key: SortKey) => {
    setSortDir((d) => (sortKey === key ? (d === "asc" ? "desc" : "asc") : "asc"));
    setSortKey(key);
  };

  const sortedResults = useMemo(() => {
    const arr = [...results];
    const mult = sortDir === "asc" ? 1 : -1;
    arr.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "query_text":
          cmp = a.query_text.localeCompare(b.query_text);
          break;
        case "refused":
          cmp = (a.refused ? 1 : 0) - (b.refused ? 1 : 0);
          break;
        case "citation_ok":
          cmp = (a.citation_ok ? 1 : 0) - (b.citation_ok ? 1 : 0);
          break;
        case "evidence_count":
          cmp = a.evidence_count - b.evidence_count;
          break;
        case "avg_confidence":
          cmp = a.avg_confidence - b.avg_confidence;
          break;
        case "top_cited_urls":
          const aLen = Array.isArray(a.top_cited_urls)
            ? a.top_cited_urls.length
            : a.top_cited_urls && typeof a.top_cited_urls === "object"
              ? Object.keys(a.top_cited_urls as Record<string, unknown>).length
              : 0;
          const bLen = Array.isArray(b.top_cited_urls)
            ? b.top_cited_urls.length
            : b.top_cited_urls && typeof b.top_cited_urls === "object"
              ? Object.keys(b.top_cited_urls as Record<string, unknown>).length
              : 0;
          cmp = aLen - bLen;
          break;
      }
      return mult * cmp;
    });
    return arr;
  }, [results, sortKey, sortDir]);

  const applyFilters = () => {
    const base = `/tenants/${encodeURIComponent(tenantId ?? "")}/worst-queries`;
    const q = new URLSearchParams();
    if (domain.trim()) q.set("domain", domain.trim());
    q.set("failed_only", String(failedOnly));
    q.set("refused_only", String(refusedOnly));
    const qs = q.toString();
    router.push(qs ? `${base}?${qs}` : base);
  };

  const SortHeader = ({
    col,
    label,
  }: {
    col: SortKey;
    label: string;
  }) => (
    <th
      className="cursor-pointer select-none px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:bg-gray-100"
      onClick={() => handleSort(col)}
    >
      {label}
      {sortKey === col && (
        <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>
      )}
    </th>
  );

  if (!tenantId || loading) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Worst Queries</h1>
        <div className="mb-4 flex flex-wrap gap-4">
          <div className="h-9 w-48 animate-pulse rounded border border-gray-200 bg-gray-100" />
          <div className="h-9 w-24 animate-pulse rounded border border-gray-200 bg-gray-100" />
          <div className="h-9 w-24 animate-pulse rounded border border-gray-200 bg-gray-100" />
        </div>
        <div className="animate-pulse overflow-hidden rounded-lg border border-gray-200">
          <div className="h-64 bg-gray-50" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Worst Queries</h1>
        <p className="text-red-600" role="alert">{error}</p>
      </div>
    );
  }

  const basePath = `/tenants/${encodeURIComponent(tenantId)}`;

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold">Worst Queries</h1>

      <div className="mb-4 flex flex-wrap items-center gap-4">
        <input
          type="text"
          placeholder="Filter by domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={failedOnly}
            onChange={(e) => setFailedOnly(e.target.checked)}
          />
          Failed only
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={refusedOnly}
            onChange={(e) => setRefusedOnly(e.target.checked)}
          />
          Refused only
        </label>
        <button
          type="button"
          onClick={applyFilters}
          className="rounded bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700"
        >
          Apply
        </button>
      </div>

      {!runId ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <p className="text-gray-600">No eval runs yet.</p>
          <p className="mt-1 text-sm text-gray-500">Run an eval to see query results.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full">
            <thead className="bg-gray-50">
              <tr>
                <SortHeader col="query_text" label="Query" />
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Domain
                </th>
                <SortHeader col="refused" label="Refused" />
                <SortHeader col="citation_ok" label="Citation OK" />
                <SortHeader col="evidence_count" label="Evidence" />
                <SortHeader col="avg_confidence" label="Confidence" />
                <SortHeader col="top_cited_urls" label="Cited URLs" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {sortedResults.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                    No results match the filters.
                  </td>
                </tr>
              ) : (
                sortedResults.map((r) => (
                  <tr key={r.query_id} className="hover:bg-gray-50">
                    <td className="max-w-xs truncate px-4 py-3 text-sm text-gray-900" title={r.query_text}>
                      {r.query_text}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      <Link
                        href={`${basePath}/worst-queries?domain=${encodeURIComponent(r.domain)}&failed_only=${failedOnly}&refused_only=${refusedOnly}`}
                        className="text-blue-600 hover:underline"
                      >
                        {r.domain}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className={r.refused ? "text-red-600" : "text-gray-600"}>
                        {r.refused ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className={r.citation_ok ? "text-green-600" : "text-gray-600"}>
                        {r.citation_ok ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{r.evidence_count}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {r.avg_confidence.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {formatUrls(r.top_cited_urls)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
