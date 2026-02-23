/**
 * Auth helpers for dashboard.
 * Token stored in cookie auth_token (set by /api/auth/login).
 */

/** Client-only: reads auth_token from document.cookie. */
export function getTokenClient(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/auth_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

/** Server-only: reads auth_token from next/headers cookies(). Use in Server Components. */
export async function getTokenServer(): Promise<string | null> {
  const { cookies } = await import("next/headers");
  const store = await cookies();
  return store.get("auth_token")?.value ?? null;
}
