"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { LeakageLatestResponse } from "@/lib/types";

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
        <h1 className="mb-6 text-xl font-semibold">Leakage</h1>
        <div className="animate-pulse rounded-lg border border-gray-200 bg-white p-6">
          <div className="mb-4 h-6 w-32 rounded bg-gray-200" />
          <div className="h-4 w-48 rounded bg-gray-200" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Leakage</h1>
        <p className="text-red-600" role="alert">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Leakage</h1>
        <p className="text-gray-600">No leakage data available.</p>
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

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold">Leakage</h1>

      <div
        className={`mb-6 rounded-lg border p-6 ${
          data.ok
            ? "border-green-200 bg-green-50"
            : "border-red-200 bg-red-50"
        }`}
      >
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-medium ${
              data.ok
                ? "bg-green-100 text-green-800"
                : "bg-red-100 text-red-800"
            }`}
          >
            {data.ok ? "OK" : "Fail"}
          </span>
          <span className="text-sm text-gray-600">
            Last checked: {formatDate(data.last_checked_at)}
          </span>
        </div>
        {!data.ok && details && typeof details === "object" && "reason" in details && (
          <p className="mt-2 text-sm text-gray-700">
            {(details as { reason?: string }).reason}
          </p>
        )}
      </div>

      {hasTable && (urls.length > 0 || sectionIds.length > 0) && (
        <div className="space-y-4">
          {urls.length > 0 && (
            <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
              <h2 className="border-b border-gray-200 bg-gray-50 px-4 py-2 text-sm font-semibold text-gray-900">
                Offending URLs
              </h2>
              <table className="min-w-full">
                <tbody className="divide-y divide-gray-200">
                  {urls.map((url, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="max-w-md truncate px-4 py-2 text-sm text-gray-900" title={url}>
                        {url}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {sectionIds.length > 0 && (
            <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
              <h2 className="border-b border-gray-200 bg-gray-50 px-4 py-2 text-sm font-semibold text-gray-900">
                Offending section IDs
              </h2>
              <table className="min-w-full">
                <tbody className="divide-y divide-gray-200">
                  {sectionIds.map((id, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-sm text-gray-900">
                        {id}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
