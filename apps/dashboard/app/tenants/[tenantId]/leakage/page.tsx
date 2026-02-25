"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { LeakageLatestResponse } from "@/lib/types";
import { ShieldCheck, ShieldAlert, AlertTriangle } from "lucide-react";
import { motion } from "framer-motion";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function isDetailsWithTable(
  d: Record<string, unknown> | unknown[] | null
): d is Record<string, unknown> & { urls?: unknown; section_ids?: unknown } {
  return d != null && typeof d === "object" && !Array.isArray(d);
}

export default function LeakagePage() {
  const params = useParams();
  const tenantId = params?.tenantId as string | undefined;
  const [data, setData] = useState<LeakageLatestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiFetch<LeakageLatestResponse>("/monitor/leakage/latest")
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load leakage status");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  if (!tenantId || loading) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Leakage</h1>
        <div className="card animate-pulse p-8">
          <div className="mb-4 flex justify-center">
            <div className="h-24 w-24 rounded-full bg-gray-200" />
          </div>
          <div className="mx-auto h-4 w-48 rounded bg-gray-200" />
          <div className="mx-auto mt-3 h-3 w-64 rounded bg-gray-100" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Leakage</h1>
        <div className="card border-rose-200 bg-rose-50/50 p-6">
          <p className="text-rose-700" role="alert">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Leakage</h1>
        <div className="card p-6">
          <p className="text-gray-600">No leakage data available.</p>
        </div>
      </div>
    );
  }

  const details = data.details_json;
  const hasTable = isDetailsWithTable(details) && (
    (Array.isArray(details.urls) && details.urls.length > 0) ||
    (Array.isArray(details.section_ids) && details.section_ids.length > 0)
  );
  const urls = hasTable && Array.isArray((details as { urls?: unknown }).urls)
    ? (details as { urls: string[] }).urls
    : [];
  const sectionIds = hasTable && Array.isArray((details as { section_ids?: unknown }).section_ids)
    ? (details as { section_ids: string[] }).section_ids
    : [];
  const reason = details && typeof details === "object" && "reason" in details
    ? (details as { reason?: string }).reason
    : undefined;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-gray-900">Leakage</h1>

      {data.ok ? (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="card flex flex-col items-center justify-center py-12 text-center"
        >
          <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-emerald-100">
            <ShieldCheck className="h-10 w-10 text-emerald-600" />
          </div>
          <h2 className="text-lg font-semibold text-gray-900">No cross-tenant leakage detected</h2>
          <p className="mt-1 text-sm text-gray-500">
            Last checked: {formatDate(data.last_checked_at)}
          </p>
          <p className="mt-4 max-w-md text-sm text-gray-600">
            Your tenant data is isolated. No content from other tenants was found in retrieval results.
          </p>
        </motion.div>
      ) : (
        <>
          <div className="mb-6 overflow-hidden rounded-xl border-2 border-rose-200 bg-rose-50 shadow-md">
            <div className="flex items-center gap-3 border-b border-rose-200 bg-rose-100/80 px-6 py-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-200">
                <ShieldAlert className="h-5 w-5 text-rose-700" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-rose-900">Cross-tenant leakage detected</h2>
                <p className="text-sm text-rose-700">Immediate review required</p>
              </div>
            </div>
            <div className="px-6 py-4">
              {reason && (
                <div className="mb-4 flex items-start gap-2 rounded-lg bg-white/80 p-3">
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
                  <p className="text-sm text-rose-800">{reason}</p>
                </div>
              )}
              <p className="text-xs text-rose-700/90">Last checked: {formatDate(data.last_checked_at)}</p>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-card">
            <h2 className="border-b border-gray-200 bg-gray-50 px-4 py-3 text-sm font-semibold text-gray-900">
              Violations
            </h2>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50/80">
                    <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                      Timestamp
                    </th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                      Type
                    </th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                      Severity
                    </th>
                    <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                      Detail
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {urls.map((url, i) => (
                    <tr key={`url-${i}`} className="hover:bg-gray-50/80">
                      <td className="whitespace-nowrap px-4 py-2.5 text-sm text-gray-600">
                        {formatDate(data.last_checked_at)}
                      </td>
                      <td className="px-4 py-2.5 text-sm font-medium text-gray-900">Offending URL</td>
                      <td className="px-4 py-2.5">
                        <span className="inline-flex rounded-md bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">
                          High
                        </span>
                      </td>
                      <td className="max-w-md truncate px-4 py-2.5 text-sm text-gray-700" title={url}>
                        {url}
                      </td>
                    </tr>
                  ))}
                  {sectionIds.map((id, i) => (
                    <tr key={`section-${i}`} className="hover:bg-gray-50/80">
                      <td className="whitespace-nowrap px-4 py-2.5 text-sm text-gray-600">
                        {formatDate(data.last_checked_at)}
                      </td>
                      <td className="px-4 py-2.5 text-sm font-medium text-gray-900">Section ID</td>
                      <td className="px-4 py-2.5">
                        <span className="inline-flex rounded-md bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">
                          High
                        </span>
                      </td>
                      <td className="font-mono text-sm text-gray-700">{id}</td>
                    </tr>
                  ))}
                  {!hasTable && (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-500">
                        No violation details available.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
