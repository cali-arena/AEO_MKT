"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

export default function HealthPage() {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    apiFetch<HealthResponse>("/health")
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Health check failed");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <div className="animate-pulse rounded-lg border border-gray-200 bg-white p-6">
          <div className="h-4 w-32 rounded bg-gray-200" />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="font-medium text-red-800">API unhealthy</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
          <p className="mt-2 text-xs text-gray-600">
            Ensure <code className="rounded bg-gray-200 px-1">NEXT_PUBLIC_API_BASE</code> points to a
            running backend.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="rounded-lg border border-green-200 bg-green-50 p-6">
        <p className="font-medium text-green-800">API healthy</p>
        {data && (
          <dl className="mt-2 space-y-1 text-sm text-gray-700">
            <dt className="font-medium">Version</dt>
            <dd>{data.version}</dd>
            <dt className="font-medium">Time</dt>
            <dd>{data.time}</dd>
          </dl>
        )}
      </div>
    </main>
  );
}
