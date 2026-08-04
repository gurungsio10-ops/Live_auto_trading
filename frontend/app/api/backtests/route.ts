import { NextRequest, NextResponse } from "next/server";
import { adminHeaders, backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
import type { BacktestReport, BacktestRequest } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<BacktestReport[]>("/backtests");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(
        demoState.backtests,
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}

export async function POST(req: NextRequest) {
  const body = (await req.json()) as BacktestRequest;

  try {
    const data = await backendFetch<BacktestReport>("/backtests", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
      timeoutMs: 30000,
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    // Fail closed — never invent backtest metrics.
    return NextResponse.json(
      envelope(null, false, err instanceof Error ? err.message : "backend down"),
      { status: 503 },
    );
  }
}
