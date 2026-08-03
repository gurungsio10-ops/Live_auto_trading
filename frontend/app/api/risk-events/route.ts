import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
import type { RiskEvent } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<RiskEvent[]>("/risk-events");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(
        demoState.riskEvents,
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
