/**
 * Single API client for all dashboard → backend calls.
 * Uses NEXT_PUBLIC_API_BASE only (no hardcoded hostnames).
 * Every request includes Authorization: "Bearer tenant:<tenantId>" (or token from cookie).
 */

import { getTokenClient, getTokenServer } from "./auth";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/$/, "");
const DEFAULT_AUTH_TOKEN = process.env.NEXT_PUBLIC_API_AUTH_TOKEN || "tenant:A";

/** For debugging: returns the API base URL used by this build. */
export function getApiBase(): string {
  return API_BASE;
}

/** Build full request URL (for logging). Uses only API_BASE, no other hostnames. */
export function getApiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
    public url?: string,
    public method: string = "GET"
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type ApiFetchInit = RequestInit & {
  /** Tenant for Authorization: Bearer tenant:<tenantId>. Pass from page/layout. */
  tenantId?: string;
};

async function getToken(): Promise<string | null> {
  if (typeof window !== "undefined") {
    return getTokenClient();
  }
  return getTokenServer();
}

/**
 * Single wrapper for all backend requests.
 * - URL: always NEXT_PUBLIC_API_BASE + path (no localhost or other hosts).
 * - Authorization: always sent (token from cookie, or Bearer tenant:<tenantId>, or Bearer tenant:A).
 * - 401: throws with message suitable for "Missing auth header" UI.
 * - 404: throws after logging exact method and URL to console.
 */
export async function apiFetch<T>(path: string, init?: ApiFetchInit): Promise<T> {
  if (!API_BASE) {
    throw new ApiError("NEXT_PUBLIC_API_BASE is not configured", 500);
  }

  const method = (init?.method || "GET").toUpperCase();
  const pathNorm = path.startsWith("/") ? path : `/${path}`;
  const url = `${API_BASE}${pathNorm}`;

  const tenantId = init?.tenantId;
  const token = await getToken();
  const authHeader =
    token ? `Bearer ${token}` : tenantId ? `Bearer tenant:${tenantId}` : `Bearer ${DEFAULT_AUTH_TOKEN}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
    Authorization: authHeader,
  };
  if (init?.headers) {
    const h = init.headers;
    if (h instanceof Headers) {
      h.forEach((v, k) => {
        headers[k] = v;
      });
    } else if (Array.isArray(h)) {
      h.forEach(([k, v]) => {
        headers[k] = v;
      });
    } else {
      Object.assign(headers, h);
    }
  }

  const requestInit: RequestInit = { ...init };
  delete (requestInit as ApiFetchInit).tenantId;

  const res = await fetch(url, { ...requestInit, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    let detail: string =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : res.statusText || "Request failed";

    if (res.status === 401) {
      detail = "Missing auth header. Use Authorization: Bearer tenant:<tenant_id> or log in.";
    } else if (res.status === 403) {
      detail = "Forbidden. Check tenant or token.";
    } else if (res.status === 404) {
      if (typeof console !== "undefined" && console.error) {
        console.error("[API 404]", method, url);
      }
      detail = `Not found: ${method} ${pathNorm}`;
    }

    throw new ApiError(detail, res.status, body, url, method);
  }

  return res.json() as Promise<T>;
}
