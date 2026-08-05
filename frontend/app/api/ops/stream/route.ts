import { NextResponse } from "next/server";
import { resolveBackendUrl } from "@/lib/runtime";

/**
 * Proxy SSE from FastAPI /ops/stream. Browser never talks to backend directly.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  try {
    const upstream = await fetch(`${resolveBackendUrl()}/ops/stream`, {
      headers: { Accept: "text/event-stream" },
      cache: "no-store",
    });
    if (!upstream.ok || !upstream.body) {
      return NextResponse.json(
        { detail: `Upstream SSE unavailable (${upstream.status})` },
        { status: 503 },
      );
    }
    return new NextResponse(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (err) {
    return NextResponse.json(
      {
        detail: err instanceof Error ? err.message : "SSE proxy failed",
      },
      { status: 503 },
    );
  }
}
