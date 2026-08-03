import { NextRequest, NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as { enabled: boolean };

  try {
    const data = await backendFetch<{ kill_switch_enabled: boolean }>("/kill-switch", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    demoState.portfolio.kill_switch_enabled = body.enabled;
    demoState.settings.kill_switch_enabled = body.enabled;
    if (body.enabled) {
      demoState.riskEvents = [
        {
          id: `risk_${Date.now().toString(36)}`,
          timestamp: new Date().toISOString(),
          decision: "HALTED",
          reason_code: "KILL_SWITCH_ACTIVE",
          message: "Kill switch engaged from dashboard.",
          symbol: null,
          strategy_name: null,
          requested_quantity: null,
          approved_quantity: null,
          order_id: null,
        },
        ...demoState.riskEvents,
      ];
    }
    return NextResponse.json(
      envelope(
        { kill_switch_enabled: body.enabled },
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
