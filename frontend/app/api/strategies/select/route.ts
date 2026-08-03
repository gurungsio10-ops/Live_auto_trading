import { NextRequest, NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
import type { Strategy } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as { strategy_id: string };

  try {
    const data = await backendFetch<Strategy>("/strategies/select", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    demoState.strategies = demoState.strategies.map((s) => ({
      ...s,
      selected: s.strategy_id === body.strategy_id,
    }));
    const selected = demoState.strategies.find((s) => s.strategy_id === body.strategy_id);
    if (!selected) {
      return NextResponse.json({ error: "Strategy not found" }, { status: 404 });
    }
    return NextResponse.json(
      envelope(selected, true, err instanceof Error ? err.message : "backend down"),
    );
  }
}
