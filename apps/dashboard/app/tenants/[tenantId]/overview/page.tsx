"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import type { MetricsLatestResponse } from "@/lib/types";
import { KpiCard } from "@/components/ui/KpiCard";
import { KpiCardSkeleton } from "@/components/ui/KpiCardSkeleton";
import { LastRunPanel } from "@/components/ui/LastRunPanel";
import { LastRunPanelSkeleton } from "@/components/ui/LastRunPanelSkeleton";

const KPI_ITEMS = [
  { key: "mention_rate" as const, label: "Mention rate", format: "percent" as const },
  { key: "citation_rate" as const, label: "Citation rate", format: "percent" as const },
  { key: "attribution_accuracy" as const, label: "Attribution accuracy", format: "percent" as const },
  { key: "hallucinations" as const, label: "Hallucinations", format: "number" as const },
  { key: "composite_index" as const, label: "Composite index", format: "decimal" as const },
] as const;

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
        <h1 className="mb-6 text-xl font-semibold">Overview</h1>
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
        <h1 className="mb-6 text-xl font-semibold">Overview</h1>
        <p className="text-red-600" role="alert">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Overview</h1>
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <p className="text-gray-600">No eval runs yet.</p>
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
      <h1 className="mb-6 text-xl font-semibold">Overview</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {KPI_ITEMS.map(({ key, label, format }) => (
          <KpiCard key={key} label={label} value={kpis[key]} format={format} />
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
