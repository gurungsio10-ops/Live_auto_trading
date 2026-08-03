import { NextRequest, NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";

export const dynamic = "force-dynamic";

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  try {
    const data = await backendFetch(`/strategies/${params.id}/stop`, {
      method: "POST",
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const idx = demoState.strategies.findIndex((s) => s.strategy_id === params.id);
    if (idx < 0) {
      return NextResponse.json({ error: "Strategy not found" }, { status: 404 });
    }
    demoState.strategies[idx] = { ...demoState.strategies[idx], running: false };
    return NextResponse.json(
      envelope(
        demoState.strategies[idx],
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
