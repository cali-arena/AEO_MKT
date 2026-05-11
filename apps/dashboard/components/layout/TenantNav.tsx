"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Globe,
  TrendingUp,
  AlertCircle,
  Shield,
  Radio,
  ChevronLeft,
} from "lucide-react";
import { motion } from "framer-motion";
import { HealthScore } from "./HealthScore";

type NavItem = {
  path: string;
  label: string;
  icon: typeof LayoutDashboard;
  accent?: "emerald";
};

const NAV_ITEMS: readonly NavItem[] = [
  { path: "overview", label: "Overview", icon: LayoutDashboard },
  { path: "domains", label: "Domains", icon: Globe },
  { path: "trends", label: "Trends", icon: TrendingUp },
  { path: "worst-queries", label: "Worst Queries", icon: AlertCircle },
  { path: "leakage", label: "Leakage", icon: Shield },
  { path: "roam", label: "ROAM", icon: Radio, accent: "emerald" },
] as const;

interface TenantNavProps {
  basePath: string;
  tenantId: string;
}

export function TenantNav({ basePath, tenantId }: TenantNavProps) {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-slate-700/50 bg-[var(--sidebar-bg)]">
      <Link
        href="/"
        className="flex items-center gap-2 border-b border-slate-700/50 px-4 py-3.5 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800/50 hover:text-white"
      >
        <ChevronLeft className="h-4 w-4" />
        Dashboard
      </Link>
      <nav className="flex-1 space-y-0.5 p-3">
        {NAV_ITEMS.map(({ path, label, icon: Icon, accent }) => {
          const href = `${basePath}/${path}`;
          const isActive = pathname === href || pathname?.startsWith(href + "/");

          if (accent === "emerald") {
            // Always-on emerald treatment so the live integration stands out
            // from the muted slate nav items. Pulsing dot communicates the
            // page polls in real time even when not active.
            return (
              <Link key={href} href={href} className="relative block">
                {isActive && (
                  <motion.span
                    layoutId="sidebar-active"
                    className="absolute left-0 top-0 h-full w-1 rounded-r bg-emerald-400"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
                <span
                  className={`flex items-center gap-3 rounded-lg border-l-2 px-3 py-2.5 text-sm font-semibold transition-colors ${
                    isActive
                      ? "border-emerald-400 bg-emerald-500/15 text-emerald-100"
                      : "border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/10 hover:text-emerald-100"
                  }`}
                >
                  <Icon className="h-5 w-5 shrink-0" />
                  <span className="tracking-wide">{label}</span>
                  <span className="relative ml-auto flex h-2 w-2" aria-label="live">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                  </span>
                </span>
              </Link>
            );
          }

          return (
            <Link key={href} href={href} className="relative block">
              {isActive && (
                <motion.span
                  layoutId="sidebar-active"
                  className="absolute left-0 top-0 h-full w-1 rounded-r bg-accent"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
              <span
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-slate-800/70 text-white"
                    : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                }`}
              >
                <Icon className="h-5 w-5 shrink-0 opacity-90" />
                {label}
              </span>
            </Link>
          );
        })}
      </nav>
      <HealthScore basePath={basePath} tenantId={tenantId} />
    </aside>
  );
}
