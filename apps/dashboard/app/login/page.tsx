"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const t = token.trim();

    if (!t) {
      setError("Token is required");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: t }),
      });

      const data = (await res.json().catch(() => ({}))) as {
        error?: string;
        tenantId?: string;
      };

      if (!res.ok) {
        setError(data.error || "Login failed");
        return;
      }

      if (!data.tenantId) {
        setError("Login response missing tenant id");
        return;
      }

      router.push(`/tenants/${encodeURIComponent(data.tenantId)}/overview`);
    } catch {
      setError("Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 p-8">
      <div className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="mb-6 text-xl font-semibold">Sign in</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="token"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Token
            </label>
            <input
              id="token"
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="e.g. tenant:acme-corp or JWT"
              className="w-full rounded border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoComplete="off"
              disabled={loading}
            />
            <p className="mt-1 text-xs text-gray-500">
              Tenant is derived from the token automatically.
            </p>
          </div>
          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Continue"}
          </button>
        </form>
      </div>
    </main>
  );
}
