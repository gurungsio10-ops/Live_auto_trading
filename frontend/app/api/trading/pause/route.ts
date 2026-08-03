import { NextRequest, NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
import type { PortfolioSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as { paused: boolean };

  try {
    const data = await backendFetch<PortfolioSummary>("/trading/pause", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    demoState.portfolio.trading_paused = body.paused;
    return NextResponse.json(
      envelope(
        demoState.portfolio,
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
