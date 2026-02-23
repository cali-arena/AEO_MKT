"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import type { EvalMetricsLatestOut } from "@/lib/types";

export default function DomainsPage() {
  const params = useParams();
  const tenantId = params?.tenantId as string | undefined;
  const [data, setData] = useState<EvalMetricsLatestOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiFetch<EvalMetricsLatestOut>("/eval/metrics/latest")
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
        </div>
      </div>
    );
  }

  const domains = Object.entries(data.per_domain).sort(([a], [b]) => a.localeCompare(b));
  const basePath = `/tenants/${encodeURIComponent(tenantId)}`;

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold">Domains</h1>
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
