import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    try {
      const data = await backendFetch<Record<string, unknown>>("/api/v1/system/health");
      return NextResponse.json(envelope(data, false));
    } catch (primary) {
      if (!(primary instanceof BackendError) || primary.status < 400) throw primary;
      const data = await backendFetch<Record<string, unknown>>("/system/health");
      return NextResponse.json(envelope(data, false));
    }
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "System health unavailable";
    return NextResponse.json(envelope(null, false, message), { status: 200 });
  }
}
