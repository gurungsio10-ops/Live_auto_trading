import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const [health, ready, metrics] = await Promise.all([
      backendFetch<Record<string, unknown>>("/health", { timeoutMs: 4000 }),
      backendFetch<Record<string, unknown>>("/ready", { timeoutMs: 4000 }),
      backendFetch<Record<string, unknown>>("/metrics", { timeoutMs: 4000 }),
    ]);
    return NextResponse.json(
      envelope(
        {
          health,
          ready,
          metrics,
          banner: "PAPER TRADING — NO REAL FUNDS",
        },
        false,
      ),
    );
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "System status failed";
    return NextResponse.json(envelope(null, false, message), { status: 503 });
  }
}
