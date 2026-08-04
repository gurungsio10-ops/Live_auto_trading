import { NextRequest, NextResponse } from "next/server";
import { adminHeaders, backendFetch, envelope } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as { enabled: boolean };

  try {
    const data = await backendFetch<{ kill_switch_enabled: boolean }>("/kill-switch", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    // Fail closed — never fake a successful kill-switch when backend is down.
    return NextResponse.json(
      envelope(
        { kill_switch_enabled: null, applied: false },
        false,
        err instanceof Error ? err.message : "backend down",
      ),
      { status: 503 },
    );
  }
}
