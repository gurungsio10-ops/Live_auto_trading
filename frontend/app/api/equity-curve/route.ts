import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
import type { EquityPoint } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<EquityPoint[]>("/portfolio/equity-curve");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(
        demoState.equityCurve,
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
