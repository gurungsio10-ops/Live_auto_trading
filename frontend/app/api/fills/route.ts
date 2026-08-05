/** Proxy GET /api/v1/fills → FastAPI fills. Fail closed when backend is down. */

import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";

export async function GET() {
  try {
    const data = await backendFetch<{ items: unknown[]; total: number }>("/api/v1/fills");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(
        { items: [], total: 0 },
        false,
        err instanceof Error ? err.message : "backend down",
      ),
      { status: 503 },
    );
  }
}
