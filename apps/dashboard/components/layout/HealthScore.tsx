"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { MetricsLatestResponse } from "@/lib/types";
import { Activity } from "lucide-react";

interface HealthScoreProps {
  basePath: string;
}

function scoreFromComposite(composite: number): number {
  if (composite <= 1) return Math.round(composite * 100);
  return Math.min(100, Math.round(composite));
}

export function HealthScore({ basePath }: HealthScoreProps) {
  const [score, setScore] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiFetch<MetricsLatestResponse>("/metrics/latest")
      .then((res) => {
        if (cancelled) return;
        setScore(scoreFromComposite(res.kpis.composite_index));
      })
      .catch(() => {
        if (!cancelled) setScore(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const status = score == null ? "neutral" : score >= 70 ? "good" : score >= 40 ? "warn" : "bad";
  const dotColor = status === "good" ? "bg-emerald-500" : status === "warn" ? "bg-amber-500" : "bg-rose-500";

  return (
    <div className="border-t border-slate-700/50 p-3">
      <Link
        href={`${basePath}/overview`}
        className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors hover:bg-slate-800/50"
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800/80">
          <Activity className="h-4 w-4 text-slate-400" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Health score</p>
          {loading ? (
            <div className="h-5 w-8 animate-pulse rounded bg-slate-700/50" />
          ) : (
            <p className="flex items-center gap-2 font-semibold text-slate-200">
              <span className={`inline-block h-2 w-2 rounded-full ${score != null ? dotColor : "bg-slate-500"}`} aria-hidden />
              {score != null ? `${score}` : "—"}
            </p>
          )}
        </div>
      </Link>
    </div>
  );
}
