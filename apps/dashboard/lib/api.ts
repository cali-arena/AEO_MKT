/**
 * API client for AI MKT backend.
 * Uses NEXT_PUBLIC_API_BASE. Attaches token from cookie (client or server).
 * On Vercel (production) the env var is required; no localhost fallback.
 */

import { getTokenClient, getTokenServer } from "./auth";

// Vercel sets VERCEL=1. In production we never use localhost so the build never points to it.
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  (process.env.VERCEL === "1" ? "" : "http://localhost:8000");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getToken(): Promise<string | null> {
  if (typeof window !== "undefined") {
    return getTokenClient();
  }
  return getTokenServer();
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
  };
  if (init?.headers) {
    const h = init.headers;
    if (h instanceof Headers) {
      h.forEach((v, k) => { headers[k] = v; });
    } else if (Array.isArray(h)) {
      h.forEach(([k, v]) => { headers[k] = v; });
    } else {
      Object.assign(headers, h);
    }
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : res.statusText || "Request failed";
    throw new ApiError(detail, res.status, body);
  }

  return res.json() as Promise<T>;
}
