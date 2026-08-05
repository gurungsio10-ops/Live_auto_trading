import { NextRequest, NextResponse } from "next/server";
import { adminHeaders, backendFetch, envelope } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as { confirm?: string };
  try {
    const data = await backendFetch<Record<string, unknown>>("/api/trading/start", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    // Fail closed — never invent a running scheduler when backend is down.
    return NextResponse.json(
      envelope(null, false, err instanceof Error ? err.message : "backend down"),
      { status: 503 },
    );
  }
}
