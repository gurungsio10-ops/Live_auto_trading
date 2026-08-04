import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import type { PortfolioSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<PortfolioSummary>("/portfolio");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(
        null,
        false,
        err instanceof Error ? err.message : "backend down",
      ),
      { status: 503 },
    );
  }
}
