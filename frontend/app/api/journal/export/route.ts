import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";

export const dynamic = "force-dynamic";

type ExportPayload = {
  filename: string;
  content: string;
  content_type: string;
};

export async function GET() {
  try {
    const data = await backendFetch<ExportPayload>("/journal/export");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const payload = {
      exported_at: new Date().toISOString(),
      mode: "demo",
      portfolio: demoState.portfolio,
      positions: demoState.positions,
      orders: demoState.orders,
      risk_events: demoState.riskEvents,
    };
    const content = JSON.stringify(payload, null, 2);
    return NextResponse.json(
      envelope(
        {
          filename: `atlas-journal-${Date.now()}.json`,
          content,
          content_type: "application/json",
        } satisfies ExportPayload,
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
