import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth";
import { sessionCookieOptions } from "@/lib/runtime";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const res = NextResponse.json({ data: { ok: true }, meta: { demo: false } });
  res.cookies.set(SESSION_COOKIE, "", {
    ...sessionCookieOptions(req, 0),
    maxAge: 0,
  });
  return res;
}
