import { NextResponse } from "next/server";
import { adminHeaders, backendFetch, envelope, BackendError } from "@/lib/backend";

/**
 * Run one deterministic paper cycle via FastAPI /api/v1.
 * Admin token stays server-side (never sent to the browser).
 */
export async function POST() {
  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/paper/cycle/run", {
      method: "POST",
      body: JSON.stringify({
        symbol: "BTC/USDT",
        timeframe: "1m",
        strategy_id: "ema_crossover",
      }),
      timeoutMs: 15000,
      headers: adminHeaders(),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Paper cycle failed";
    // Fail closed — never invent a successful cycle when backend/auth fails.
    return NextResponse.json(envelope(null, false, message), { status: 503 });
  }
}
