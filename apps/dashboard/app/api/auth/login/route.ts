import { NextResponse } from "next/server";

/**
 * Decode the tenant_id encoded in the bearer token.
 *
 * Mirrors apps/api/services/auth.py:_extract_tenant_and_actor — supports the
 * two token shapes the FastAPI auth middleware accepts:
 *   1. `tenant:<id>` prefix form
 *   2. JWT with a `tenant_id` (or `tid`) claim in the payload
 *
 * Returns null when neither pattern matches. The server-side middleware
 * remains the source of truth — this helper only mirrors enough of the parse
 * so the dashboard can route to the correct `/tenants/<id>/…` URL.
 */
function deriveTenantIdFromToken(token: string): string | null {
  const trimmed = token.trim();
  if (!trimmed) return null;

  // `tenant:<id>` shape
  const prefixMatch = /^tenant:(.+)$/.exec(trimmed);
  if (prefixMatch) {
    const id = prefixMatch[1].trim();
    return id || null;
  }

  // JWT shape: three base64url segments separated by `.`
  const parts = trimmed.split(".");
  if (parts.length !== 3) return null;

  try {
    // base64url -> base64 -> JSON
    const padded = parts[1] + "===".slice((parts[1].length + 3) % 4);
    const b64 = padded.replace(/-/g, "+").replace(/_/g, "/");
    const json = Buffer.from(b64, "base64").toString("utf8");
    const payload = JSON.parse(json) as Record<string, unknown>;
    const tenant = payload.tenant_id ?? payload.tid;
    if (typeof tenant === "string" && tenant.trim()) {
      return tenant.trim();
    }
    return null;
  } catch {
    return null;
  }
}

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const token = typeof body?.token === "string" ? body.token : null;

  if (!token) {
    return NextResponse.json({ error: "token required" }, { status: 400 });
  }

  const tenantId = deriveTenantIdFromToken(token);
  if (!tenantId) {
    return NextResponse.json(
      {
        error:
          "invalid token format — expected `tenant:<id>` or a JWT with a tenant_id claim",
      },
      { status: 400 },
    );
  }

  const res = NextResponse.json({ ok: true, tenantId });
  res.cookies.set("auth_token", token, {
    path: "/",
    httpOnly: false, // MVP: allow client read for API attach
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
  });
  // Non-httpOnly so server components and the layout can read the canonical
  // tenant slug without re-decoding the token on every request.
  res.cookies.set("tenant_id", tenantId, {
    path: "/",
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
  });
  return res;
}
