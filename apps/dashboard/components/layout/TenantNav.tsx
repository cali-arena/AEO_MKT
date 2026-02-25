"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Globe,
  TrendingUp,
  AlertCircle,
  Shield,
  ChevronLeft,
} from "lucide-react";
import { motion } from "framer-motion";

const NAV_ITEMS = [
  { path: "overview", label: "Overview", icon: LayoutDashboard },
  { path: "domains", label: "Domains", icon: Globe },
  { path: "trends", label: "Trends", icon: TrendingUp },
  { path: "worst-queries", label: "Worst Queries", icon: AlertCircle },
  { path: "leakage", label: "Leakage", icon: Shield },
] as const;

interface TenantNavProps {
  basePath: string;
}

export function TenantNav({ basePath }: TenantNavProps) {
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
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const href = `${basePath}/${path}`;
          const isActive = pathname === href || pathname?.startsWith(href + "/");
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
      <HealthScore basePath={basePath} />
    </aside>
  );
}
