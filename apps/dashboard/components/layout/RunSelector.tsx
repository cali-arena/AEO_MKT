"use client";

import { useEffect, useState } from "react";
import { usePathname, useSearchParams, useRouter } from "next/navigation";
import { ChevronDown, History } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { EvalRunsResponse, EvalRunListItem } from "@/lib/types";

function formatRunLabel(run: EvalRunListItem, index: number): string {
  try {
    const d = new Date(run.created_at);
    const dateStr = d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "2-digit" });
    const timeStr = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    return index === 0 ? `Latest (${dateStr})` : `${dateStr} ${timeStr}`;
  } catch {
    return index === 0 ? "Latest" : run.run_id.slice(0, 8);
  }
}

export function RunSelector() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [runs, setRuns] = useState<EvalRunListItem[]>([]);
  const [open, setOpen] = useState(false);
  const currentRunId = searchParams.get("run_id");

  useEffect(() => {
    let cancelled = false;
    apiFetch<EvalRunsResponse>("/eval/runs?limit=15")
      .then((res) => {
        if (!cancelled) setRuns(res.runs);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const handleSelect = (runId: string) => {
    setOpen(false);
    const next = new URLSearchParams(searchParams.toString());
    next.set("run_id", runId);
    router.push(`${pathname ?? ""}?${next.toString()}`);
  };

  const currentRun = currentRunId ? runs.find((r) => r.run_id === currentRunId) : runs[0];
  const label = currentRun ? formatRunLabel(currentRun, runs.indexOf(currentRun)) : "Run";

  if (runs.length === 0) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-sm font-medium text-gray-900 shadow-card transition-shadow hover:shadow-card-hover dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
      >
        <History className="h-4 w-4 text-gray-500 dark:text-slate-400" />
        <span className="max-w-[140px] truncate">{label}</span>
        <ChevronDown className="h-4 w-4 shrink-0 text-gray-500" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" aria-hidden onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 max-h-64 w-56 overflow-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-slate-600 dark:bg-slate-800">
            {runs.map((run, i) => (
              <button
                key={run.run_id}
                type="button"
                onClick={() => handleSelect(run.run_id)}
                className={`flex w-full items-center px-3 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-slate-700 ${
                  (currentRunId === run.run_id || (!currentRunId && i === 0)) ? "bg-primary/10 font-medium text-primary dark:bg-accent/20 dark:text-accent" : "text-gray-700 dark:text-slate-300"
                }`}
              >
                {formatRunLabel(run, i)}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
