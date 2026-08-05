import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

/** Disable paper scheduler. Admin token stays server-side. */
export async function POST() {
  const adminToken = process.env.ADMIN_API_TOKEN ?? process.env.ATLAS_ADMIN_API_TOKEN;
  if (!adminToken) {
    return NextResponse.json(
      envelope(null, false, "ADMIN_API_TOKEN not configured on Next.js server"),
      { status: 200 },
    );
  }

  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/scheduler/disable", {
      method: "POST",
      headers: { "X-Admin-Token": adminToken },
      timeoutMs: 10000,
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Scheduler disable failed";
    return NextResponse.json(envelope(null, false, message), { status: 200 });
  }
}
