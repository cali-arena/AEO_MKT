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

/** For debugging: returns the API base URL used by this build (empty on Vercel if env was not set at build time). */
export function getApiBase(): string {
  return API_BASE;
}

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

export type ApiFetchInit = RequestInit & {
  tenantId?: string;
};

async function getToken(): Promise<string | null> {
  if (typeof window !== "undefined") {
    return getTokenClient();
  }
  return getTokenServer();
}

export async function apiFetch<T>(
  path: string,
  init?: ApiFetchInit
): Promise<T> {
  const tenantId = init?.tenantId;
  const token = await getToken();
  const authHeader = token
    ? `Bearer ${token}`
    : tenantId
      ? `Bearer tenant:${tenantId}`
      : undefined;
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
    ...(authHeader && { Authorization: authHeader }),
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

  const requestInit: RequestInit = { ...init };
  delete (requestInit as { tenantId?: string }).tenantId;
  const res = await fetch(`${API_BASE}${path}`, { ...requestInit, headers });

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
