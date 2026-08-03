import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

/**
 * Run one deterministic paper cycle via FastAPI /api/v1.
 * Admin token stays server-side (never sent to the browser).
 */
export async function POST() {
  const adminToken = process.env.ADMIN_API_TOKEN ?? process.env.ATLAS_ADMIN_API_TOKEN;
  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/paper/cycle/run", {
      method: "POST",
      body: JSON.stringify({
        symbol: "BTC/USDT",
        timeframe: "1m",
        strategy_id: "ema_crossover",
      }),
      timeoutMs: 15000,
      headers: adminToken ? { "X-Admin-Token": adminToken } : {},
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Paper cycle failed";
    return NextResponse.json(envelope(null, true, message), { status: 200 });
  }
}
