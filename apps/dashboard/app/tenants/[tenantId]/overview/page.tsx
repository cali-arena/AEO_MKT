"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import type { MetricsLatestResponse } from "@/lib/types";
import { KpiCard } from "@/components/ui/KpiCard";
import { KpiCardSkeleton } from "@/components/ui/KpiCardSkeleton";
import { LastRunPanel } from "@/components/ui/LastRunPanel";
import { LastRunPanelSkeleton } from "@/components/ui/LastRunPanelSkeleton";

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

export default function OverviewPage() {
  const params = useParams();
  const tenantId = params?.tenantId as string | undefined;
  const [data, setData] = useState<MetricsLatestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiFetch<MetricsLatestResponse>("/metrics/latest")
      .then((res) => {
        if (!cancelled) {
          setData(res);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setData(null);
            setError(null);
          } else {
            setError(err instanceof Error ? err.message : "Failed to load metrics");
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

  if (loading) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Overview</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {KPI_ITEMS.map((_, i) => (
            <KpiCardSkeleton key={i} />
          ))}
        </div>
        <div className="mt-6">
          <LastRunPanelSkeleton />
        </div>
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
          <p className="text-lg text-gray-600">No eval runs yet.</p>
          <p className="mt-1 text-sm text-gray-500">
            Run an eval to see metrics and KPIs.
          </p>
        </div>
      </div>
    );
  }

  const { kpis, created_at, crawl_policy_version, ac_version_hash, ec_version_hash } = data;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-gray-900">Overview</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {KPI_ITEMS.map(({ key, label, format, accent }) => (
          <KpiCard
            key={key}
            label={label}
            value={kpis[key]}
            format={format}
            accent={accent}
          />
        ))}
      </div>
      <div className="mt-6">
        <LastRunPanel
          created_at={created_at}
          crawl_policy_version={crawl_policy_version}
          ac_version_hash={ac_version_hash}
          ec_version_hash={ec_version_hash}
        />
      </div>
    </div>
  );
}
