import { AuthGuard } from "@/components/layout/AuthGuard";
import { Header } from "@/components/layout/Header";
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
      <div className="flex min-h-screen bg-gray-50">
        <TenantNav basePath={base} />
        <div className="flex flex-1 flex-col">
          <Header tenantId={decoded} />
          <main className="flex-1 p-6">
            <div className="mx-auto max-w-6xl">{children}</div>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
