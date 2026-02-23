import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const token = typeof body?.token === "string" ? body.token : null;

  if (!token) {
    return NextResponse.json({ error: "token required" }, { status: 400 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set("auth_token", token, {
    path: "/",
    httpOnly: false, // MVP: allow client read for API attach
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
  });
  return res;
}
