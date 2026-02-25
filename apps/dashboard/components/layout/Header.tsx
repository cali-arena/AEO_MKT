"use client";

import { useMemo } from "react";
import { User, ChevronDown } from "lucide-react";

interface HeaderProps {
  tenantId: string;
  lastSync?: string | null;
}

export function Header({ tenantId, lastSync }: HeaderProps) {
  const envLabel = process.env.NODE_ENV === "production" ? "PROD" : "DEV";
  const displaySync = useMemo(() => {
    if (!lastSync) return null;
    const d = new Date(lastSync);
    if (Number.isNaN(d.getTime())) return null;
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffM = Math.floor(diffMs / 60000);
    if (diffM < 1) return "Just now";
    if (diffM < 60) return `${diffM}m ago`;
    const diffH = Math.floor(diffM / 60);
    if (diffH < 24) return `${diffH}h ago`;
    return d.toLocaleDateString();
  }, [lastSync]);

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b border-gray-200 bg-white/95 px-6 py-3 backdrop-blur supports-[backdrop-filter]:bg-white/80 dark:border-slate-700 dark:bg-slate-900/95 dark:supports-[backdrop-filter]:bg-slate-900/80">
      <div className="flex items-center gap-4">
        <div className="relative">
          <button
            type="button"
            className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-sm font-medium text-gray-900 shadow-card transition-shadow hover:shadow-card-hover"
          >
            <span className="truncate max-w-[180px]">{tenantId}</span>
            <ChevronDown className="h-4 w-4 shrink-0 text-gray-500" />
          </button>
        </div>
        <span
          className={`rounded-md px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${
            envLabel === "PROD"
              ? "bg-emerald-100 text-emerald-800"
              : "bg-amber-100 text-amber-800"
          }`}
        >
          {envLabel}
        </span>
        {displaySync && (
          <span className="text-xs text-gray-500">Last sync: {displaySync}</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <DarkModeToggle />
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary">
          <User className="h-5 w-5" />
        </div>
      </div>
    </header>
  );
}
