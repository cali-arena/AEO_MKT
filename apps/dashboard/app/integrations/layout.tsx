import { AuthGuard } from "@/components/layout/AuthGuard";
import Link from "next/link";
import { ChevronLeft, Plug } from "lucide-react";

export const metadata = { title: "Integrations — Citarion" };

export default function IntegrationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <div className="min-h-screen bg-surface dark:bg-slate-900">
        <header className="sticky top-0 z-30 border-b border-slate-700/50 bg-[var(--sidebar-bg)] px-6 py-3 flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            Dashboard
          </Link>
          <span className="text-slate-600">/</span>
          <span className="flex items-center gap-1.5 text-sm font-medium text-slate-100">
            <Plug className="h-4 w-4 text-accent" />
            Integrations
          </span>
        </header>
        <main className="mx-auto max-w-6xl p-6">{children}</main>
      </div>
    </AuthGuard>
  );
}
