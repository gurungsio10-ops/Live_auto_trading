import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, verifySessionToken } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const session = await verifySessionToken(req.cookies.get(SESSION_COOKIE)?.value);
  return NextResponse.json({
    data: {
      authenticated: Boolean(session),
      username: session?.username ?? null,
    },
    meta: { demo: false },
  });
}
