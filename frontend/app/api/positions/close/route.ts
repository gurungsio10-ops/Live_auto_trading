import { NextRequest, NextResponse } from "next/server";
import { adminHeaders, backendFetch, envelope } from "@/lib/backend";
import type { Position } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as { symbol: string };
  try {
    const data = await backendFetch<Position[]>("/positions/close", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(null, false, err instanceof Error ? err.message : "backend down"),
      { status: 503 },
    );
  }
}
