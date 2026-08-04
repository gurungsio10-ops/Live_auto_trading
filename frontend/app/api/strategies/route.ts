import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import type { Strategy } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<Strategy[]>("/strategies");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope([], false, err instanceof Error ? err.message : "backend down"),
      { status: 503 },
    );
  }
}
