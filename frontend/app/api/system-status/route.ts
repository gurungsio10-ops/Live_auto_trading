import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    try {
      const data = await backendFetch<Record<string, unknown>>("/api/v1/system/status/unified");
      return NextResponse.json(envelope(data, false));
    } catch (primary) {
      if (!(primary instanceof BackendError) || primary.status < 400) throw primary;
      const data = await backendFetch<Record<string, unknown>>("/api/v1/system/health");
      return NextResponse.json(envelope(data, false));
    }
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Unified status unavailable";
    return NextResponse.json(
      envelope(
        {
          status: "DISCONNECTED",
          system: { state: "DISCONNECTED", degraded_reasons: [message] },
          degraded_reasons: [message],
          engine: { state: "DISCONNECTED", reasons: [message] },
          kill_switch: { enabled: false, state: "OFF" },
          scheduler: { state: "DISCONNECTED" },
          market_data: { ok: false, label: "Unavailable", state: "DISCONNECTED" },
          database: { ok: false, state: "ERROR" },
        },
        false,
        message,
      ),
      { status: 200 },
    );
  }
}
