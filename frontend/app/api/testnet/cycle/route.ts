import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export async function POST() {
  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/testnet/cycle/run", {
      method: "POST",
      body: JSON.stringify({
        symbol: "BTC/USDT",
        timeframe: "1m",
        use_sample_candles: true,
      }),
      timeoutMs: 20000,
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Testnet cycle failed";
    return NextResponse.json(envelope(null, true, message), { status: 200 });
  }
}
