import { NextRequest, NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
import type { Position } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as { symbol: string };

  try {
    const data = await backendFetch<Position[]>("/positions/close", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    demoState.positions = demoState.positions.filter((p) => p.symbol !== body.symbol);
    demoState.portfolio.open_position_count = demoState.positions.length;
    return NextResponse.json(
      envelope(
        demoState.positions,
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
