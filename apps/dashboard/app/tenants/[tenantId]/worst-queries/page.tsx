"use client";

import { Fragment, useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import type { EvalRunsResponse, EvalRunResultsResponse, EvalResultRow } from "@/lib/types";
import { ChevronDown, ChevronRight, Copy, Filter } from "lucide-react";

type SortKey = "query_text" | "domain" | "refused" | "citation_ok" | "evidence_count" | "avg_confidence" | "risk_score";
type SortDir = "asc" | "desc";

function riskScore(r: EvalResultRow): number {
  let s = 0;
  if (r.refused) s += 40;
  if (!r.mention_ok) s += 20;
  if (!r.citation_ok) s += 20;
  if (!r.attribution_ok) s += 10;
  if (r.hallucination_flag) s += 30;
  return Math.min(100, s);
}

function formatUrls(val: Record<string, unknown> | unknown[] | null): string {
  if (val == null) return "—";
  if (Array.isArray(val)) return val.length > 0 ? `${val.length} cited` : "—";
  const obj = val as Record<string, unknown>;
  return Object.keys(obj).length > 0 ? `${Object.keys(obj).length} cited` : "—";
}

export default function WorstQueriesPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const tenantId = params?.tenantId as string | undefined;

  const domainParam = searchParams.get("domain") ?? "";
  const failedOnlyParam = searchParams.get("failed_only");
  const refusedOnlyParam = searchParams.get("refused_only");
  const hallucinationsOnlyParam = searchParams.get("hallucinations_only");
  const runIdParam = searchParams.get("run_id");

  const [domain, setDomain] = useState(domainParam);
  const [failedOnly, setFailedOnly] = useState(failedOnlyParam !== "false");
  const [refusedOnly, setRefusedOnly] = useState(refusedOnlyParam === "true");
  const [hallucinationsOnly, setHallucinationsOnly] = useState(hallucinationsOnlyParam === "true");
  const [runId, setRunId] = useState<string | null>(null);
  const [results, setResults] = useState<EvalResultRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("risk_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    setDomain(domainParam);
    setFailedOnly(failedOnlyParam !== "false");
    setRefusedOnly(refusedOnlyParam === "true");
    setHallucinationsOnly(hallucinationsOnlyParam === "true");
  }, [domainParam, failedOnlyParam, refusedOnlyParam, hallucinationsOnlyParam]);

  useEffect(() => {
    if (!tenantId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetch<EvalRunsResponse>("/eval/runs?limit=15")
      .then((runsRes) => {
        if (cancelled) return;
        const runs = runsRes.runs;
        const run = runIdParam
          ? runs.find((r) => r.run_id === runIdParam) ?? runs[0]
          : runs[0];
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
        let list = resultsRes.results;
        if (hallucinationsOnlyParam === "true") {
          list = list.filter((r) => r.hallucination_flag);
        }
        setResults(list);
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
  }, [tenantId, runIdParam, domainParam, failedOnlyParam, refusedOnlyParam, hallucinationsOnlyParam]);

  const handleSort = (key: SortKey) => {
    setSortDir((d) => (sortKey === key ? (d === "asc" ? "desc" : "asc") : "desc"));
    setSortKey(key);
  };

  const sortedResults = useMemo(() => {
    const arr = [...results].map((r) => ({ ...r, risk_score: riskScore(r) }));
    const mult = sortDir === "asc" ? 1 : -1;
    arr.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "query_text":
          cmp = a.query_text.localeCompare(b.query_text);
          break;
        case "domain":
          cmp = a.domain.localeCompare(b.domain);
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
        case "risk_score":
          cmp = a.risk_score - b.risk_score;
          break;
        default:
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
    if (hallucinationsOnly) q.set("hallucinations_only", "true");
    const qs = q.toString();
    router.push(qs ? `${base}?${qs}` : base);
  };

  const copyQuery = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const exportCsv = () => {
    const headers = ["query_id", "domain", "query_text", "refused", "citation_ok", "hallucination_flag", "evidence_count", "risk_score"];
    const rows = sortedResults.map((r) =>
      [r.query_id, r.domain, `"${r.query_text.replace(/"/g, '""')}"`, r.refused, r.citation_ok, r.hallucination_flag, r.evidence_count, riskScore(r)].join(",")
    );
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `worst-queries-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const basePath = `/tenants/${encodeURIComponent(tenantId ?? "")}`;

  if (!tenantId || loading) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Worst Queries</h1>
        <div className="card animate-pulse p-6">
          <div className="mb-4 h-10 w-64 rounded bg-gray-200" />
          <div className="h-64 rounded bg-gray-100" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Worst Queries</h1>
        <div className="card rounded-xl border-rose-200 bg-rose-50/50 p-4">
          <p className="text-rose-700" role="alert">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-gray-900">Worst Queries</h1>

      <div className="card mb-4 flex flex-wrap items-center gap-3 p-4">
        <Filter className="h-4 w-4 text-gray-500" />
        <input
          type="text"
          placeholder="Filter by domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        />
        <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)} className="rounded border-gray-300" />
          Failed only
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={refusedOnly} onChange={(e) => setRefusedOnly(e.target.checked)} className="rounded border-gray-300" />
          Refused only
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={hallucinationsOnly} onChange={(e) => setHallucinationsOnly(e.target.checked)} className="rounded border-gray-300" />
          Hallucinations only
        </label>
        <button
          type="button"
          onClick={applyFilters}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary/90"
        >
          Apply
        </button>
        <button
          type="button"
          onClick={exportCsv}
          className="ml-auto rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Export CSV
        </button>
      </div>

      {!runId ? (
        <div className="card rounded-xl border-dashed border-gray-300 bg-gray-50/50 p-12 text-center">
          <p className="text-lg text-gray-600">No eval runs yet.</p>
          <p className="mt-1 text-sm text-gray-500">Run an eval to see query results.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="min-w-full">
            <thead className="bg-gray-50/80">
              <tr>
                <th className="w-8 px-2 py-3" />
                <th className="cursor-pointer select-none px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:text-gray-900" onClick={() => handleSort("query_text")}>
                  Query {sortKey === "query_text" && (sortDir === "asc" ? "↑" : "↓")}
                </th>
                <th className="cursor-pointer select-none px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:text-gray-900" onClick={() => handleSort("domain")}>
                  Domain {sortKey === "domain" && (sortDir === "asc" ? "↑" : "↓")}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Mention</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Citation</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Evidence</th>
                <th className="cursor-pointer select-none px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:text-gray-900" onClick={() => handleSort("risk_score")}>
                  Risk {sortKey === "risk_score" && (sortDir === "asc" ? "↑" : "↓")}
                </th>
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
                sortedResults.map((r) => {
                  const risk = riskScore(r);
                  const isExpanded = expandedId === r.query_id;
                  return (
                    <Fragment key={r.query_id}>
                      <tr
                        className={`cursor-pointer transition-colors hover:bg-gray-50 ${risk >= 50 ? "bg-amber-50/50" : ""}`}
                        onClick={() => setExpandedId(isExpanded ? null : r.query_id)}
                      >
                        <td className="w-8 px-2 py-3">
                          {isExpanded ? <ChevronDown className="h-4 w-4 text-gray-500" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
                        </td>
                        <td className="max-w-md px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm text-gray-900" title={r.query_text}>{r.query_text}</span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                copyQuery(r.query_text);
                              }}
                              className="shrink-0 rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
                            >
                              <Copy className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <Link href={`${basePath}/worst-queries?domain=${encodeURIComponent(r.domain)}`} className="text-primary hover:underline" onClick={(e) => e.stopPropagation()}>
                            {r.domain}
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${r.mention_ok ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`}>
                            {r.mention_ok ? "OK" : "Fail"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${r.citation_ok ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
                            {r.citation_ok ? "OK" : "Fail"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">{r.evidence_count}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${risk >= 50 ? "bg-rose-100 text-rose-800" : risk >= 20 ? "bg-amber-100 text-amber-800" : "bg-gray-100 text-gray-700"}`}>
                            {risk}
                          </span>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-gray-50/80">
                          <td colSpan={7} className="px-4 py-3">
                            <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 text-sm">
                              <div>
                                <p className="text-xs font-medium uppercase text-gray-500">Answer preview</p>
                                <p className="mt-1 max-h-24 overflow-y-auto text-gray-700">{r.answer_preview || "—"}</p>
                              </div>
                              <div>
                                <p className="text-xs font-medium uppercase text-gray-500">Top cited URLs</p>
                                <p className="mt-1 text-gray-600">{formatUrls(r.top_cited_urls)}</p>
                                {r.top_cited_urls && typeof r.top_cited_urls === "object" && !Array.isArray(r.top_cited_urls) && (
                                  <ul className="mt-1 list-inside list-disc text-xs text-gray-500">
                                    {Object.entries(r.top_cited_urls as Record<string, string>).slice(0, 5).map(([k, v]) => (
                                      <li key={k} className="truncate" title={v}>{v}</li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
