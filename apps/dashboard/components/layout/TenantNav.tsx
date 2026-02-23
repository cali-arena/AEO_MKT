import Link from "next/link";

const NAV_ITEMS = [
  { path: "overview", label: "Overview" },
  { path: "domains", label: "Domains" },
  { path: "trends", label: "Trends" },
  { path: "worst-queries", label: "Worst Queries" },
  { path: "leakage", label: "Leakage" },
] as const;

interface TenantNavProps {
  basePath: string;
}

export function TenantNav({ basePath }: TenantNavProps) {
  return (
    <aside className="flex w-56 flex-col border-r border-gray-200 bg-gray-50">
      <Link
        href="/"
        className="border-b border-gray-200 px-4 py-3 text-sm font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900"
      >
        ← Dashboard
      </Link>
      <nav className="flex-1 space-y-0.5 p-2">
        {NAV_ITEMS.map(({ path, label }) => {
          const href = `${basePath}/${path}`;
          return (
            <Link
              key={href}
              href={href}
              className="block rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-200 hover:text-gray-900"
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
