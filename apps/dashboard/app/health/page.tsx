"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError, getApiBase } from "@/lib/api";
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
    const apiBase = getApiBase();
    const isVercel = typeof window !== "undefined" && /\.vercel\.app$/i.test(window.location.hostname);
    const missingBase = isVercel && !apiBase;

    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <div className="max-w-md rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="font-medium text-red-800">API unhealthy</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
          <p className="mt-2 text-xs text-gray-600">
            Current API base: <code className="rounded bg-gray-200 px-1">{apiBase || "(not set)"}</code>
          </p>
          {missingBase && (
            <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-medium">Env not applied in this build</p>
              <p className="mt-1 text-xs">
                Set <code>NEXT_PUBLIC_API_BASE</code> in Vercel → Settings → Environment Variables (tunnel URL, no trailing slash),
                then <strong>Redeploy</strong> — the value is baked at build time. Saving the variable alone does not update the live site.
              </p>
            </div>
          )}
          {!missingBase && (
            <p className="mt-2 text-xs text-gray-600">
              Ensure the backend and tunnel are running and CORS allows this origin.
            </p>
          )}
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
