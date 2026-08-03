import { NextRequest, NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";

export const dynamic = "force-dynamic";

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const body = (await req.json()) as {
    paper_params: Record<string, string | number | boolean>;
  };

  try {
    const data = await backendFetch(`/strategies/${params.id}/params`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const idx = demoState.strategies.findIndex((s) => s.strategy_id === params.id);
    if (idx < 0) {
      return NextResponse.json({ error: "Strategy not found" }, { status: 404 });
    }
    const strategy = demoState.strategies[idx];
    if (strategy.governance_status !== "PAPER" && strategy.governance_status !== "TESTNET") {
      return NextResponse.json(
        { error: "Paper params only editable for PAPER/TESTNET strategies" },
        { status: 400 },
      );
    }
    demoState.strategies[idx] = {
      ...strategy,
      paper_params: { ...body.paper_params },
    };
    return NextResponse.json(
      envelope(
        demoState.strategies[idx],
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
