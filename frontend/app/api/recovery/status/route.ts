import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<Record<string, unknown>>(
      "/api/v1/recovery/status",
      { timeoutMs: 5000 },
    );
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message =
      err instanceof BackendError ? err.message : "Recovery status failed";
    return NextResponse.json(envelope(null, false, message), { status: 503 });
  }
}
