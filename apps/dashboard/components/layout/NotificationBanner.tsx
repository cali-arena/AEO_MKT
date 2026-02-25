"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { MetricsLatestResponse } from "@/lib/types";
import { AlertTriangle, X } from "lucide-react";

interface NotificationBannerProps {
  basePath: string;
}

export function NotificationBanner({ basePath }: NotificationBannerProps) {
  const [dismissed, setDismissed] = useState(false);
  const [alerts, setAlerts] = useState< string[]>([]);

  useEffect(() => {
    let cancelled = false;
    apiFetch<MetricsLatestResponse>("/metrics/latest")
      .then((res) => {
        if (cancelled) return;
        const list: string[] = [];
        if (res.kpis.citation_rate < 0.7) {
          list.push("Citation rate below 70%");
        }
        if (res.kpis.mention_rate < 0.5) {
          list.push("Mention rate below 50%");
        }
        if ((res.kpis.hallucinations ?? 0) > 0) {
          list.push("Hallucinations detected");
        }
        setAlerts(list);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (dismissed || alerts.length === 0) return null;

  return (
    <div className="flex items-center justify-between gap-4 border-b border-amber-200 bg-amber-50 px-6 py-2.5 dark:border-amber-900/50 dark:bg-amber-950/30">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-500" />
        <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
          {alerts.length === 1 ? alerts[0] : "Multiple issues detected"} —{" "}
          <Link href={`${basePath}/overview`} className="underline hover:no-underline">
            View overview
          </Link>
        </p>
      </div>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="rounded p-1 text-amber-600 hover:bg-amber-200/80 dark:text-amber-400 dark:hover:bg-amber-800/50"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
