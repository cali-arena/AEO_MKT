"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, ApiError } from "@/lib/api";
import type { MetricsTrendsResponse, MetricsTrendPoint } from "@/lib/types";
import { LineMetricChart } from "@/components/charts/LineMetricChart";

function parsePoint(raw: Record<string, unknown>): MetricsTrendPoint {
  const num = (v: unknown): number => {
    if (typeof v === "number" && !Number.isNaN(v)) return v;
    const n = parseFloat(String(v));
    return Number.isNaN(n) ? 0 : n;
  };
  const runId = raw.run_id;
  return {
    ts: typeof raw.ts === "string" ? raw.ts : "",
    mention_rate: num(raw.mention_rate),
    citation_rate: num(raw.citation_rate),
    attribution_accuracy: num(raw.attribution_accuracy),
    hallucinations: num(raw.hallucinations),
    composite_index: num(raw.composite_index),
    run_id: runId != null ? String(runId) : null,
  };
}

const CHART_CONFIGS = [
  { yKey: "mention_rate" as const, title: "Mention rate", label: "Mention rate" },
  { yKey: "citation_rate" as const, title: "Citation rate", label: "Citation rate" },
  { yKey: "attribution_accuracy" as const, title: "Attribution accuracy", label: "Attribution accuracy" },
  {
    yKey: "hallucinations" as const,
    title: "Hallucinations",
    label: "Hallucinations",
    yDomain: ["auto", "auto"] as [number | "auto", number | "auto"],
    yTickFormatter: (v: number) => String(Math.round(v)),
    valueFormatter: (v: number) => String(Math.round(v)),
  },
] as const;

export default function TrendsPage() {
  const params = useParams();
  const tenantId = params?.tenantId as string | undefined;
  const [data, setData] = useState<MetricsTrendsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiFetch<MetricsTrendsResponse>("/metrics/trends?days=30")
      .then((res) => {
        if (!cancelled) {
          const points = (res.points ?? []).map((p) =>
            parsePoint(p as unknown as Record<string, unknown>)
          );
          setData({ ...res, points });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setData({ tenant_id: tenantId, points: [] });
            setError(null);
          } else {
            setError(err instanceof Error ? err.message : "Failed to load trends");
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
        <h1 className="mb-6 text-xl font-semibold">Trends</h1>
        <div className="grid gap-6 sm:grid-cols-1 lg:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="animate-pulse rounded-lg border border-gray-200 bg-white p-4">
              <div className="mb-4 h-4 w-32 rounded bg-gray-200" />
              <div className="h-64 rounded bg-gray-100" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Trends</h1>
        <p className="text-red-600" role="alert">{error}</p>
      </div>
    );
  }

  const points = data?.points ?? [];
  const chartData = points.map((p) => ({
    ts: p.ts,
    mention_rate: p.mention_rate,
    citation_rate: p.citation_rate,
    attribution_accuracy: p.attribution_accuracy,
    hallucinations: p.hallucinations,
  }));

  if (chartData.length === 0) {
    return (
      <div>
        <h1 className="mb-6 text-xl font-semibold">Trends</h1>
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <p className="text-gray-600">No trend data yet.</p>
          <p className="mt-1 text-sm text-gray-500">
            Run evals over time to see metrics trends.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold">Trends (last 30 days)</h1>
      <div className="grid gap-6 sm:grid-cols-1 lg:grid-cols-2">
        {CHART_CONFIGS.map((cfg) => (
          <LineMetricChart
            key={cfg.yKey}
            data={chartData}
            xKey="ts"
            yKey={cfg.yKey}
            title={cfg.title}
            label={cfg.label}
            {...("yDomain" in cfg && { yDomain: cfg.yDomain })}
            {...("yTickFormatter" in cfg && { yTickFormatter: cfg.yTickFormatter })}
            {...("valueFormatter" in cfg && { valueFormatter: cfg.valueFormatter })}
          />
        ))}
      </div>
    </div>
  );
}
