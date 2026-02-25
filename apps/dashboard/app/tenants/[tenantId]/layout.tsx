import { AuthGuard } from "@/components/layout/AuthGuard";
import { Header } from "@/components/layout/Header";
import { NotificationBanner } from "@/components/layout/NotificationBanner";
import { TenantNav } from "@/components/layout/TenantNav";

export default async function TenantLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = await params;
  const decoded = decodeURIComponent(tenantId);
  const base = `/tenants/${encodeURIComponent(tenantId)}`;

  return (
    <AuthGuard>
      <div className="min-h-screen bg-surface dark:bg-slate-900">
        <TenantNav basePath={base} />
        <div className="flex flex-1 flex-col pl-60">
          <Header tenantId={decoded} />
          <NotificationBanner basePath={base} />
          <main className="flex-1 p-6">
            <div className="mx-auto max-w-6xl">{children}</div>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
