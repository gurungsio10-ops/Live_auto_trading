import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

/** Pause or resume paper scheduler. Admin token stays server-side. */
export async function POST(request: Request) {
  const adminToken = process.env.ADMIN_API_TOKEN ?? process.env.ATLAS_ADMIN_API_TOKEN;
  if (!adminToken) {
    return NextResponse.json(
      envelope(null, false, "ADMIN_API_TOKEN not configured on Next.js server"),
      { status: 200 },
    );
  }

  let paused = true;
  try {
    const body = (await request.json()) as { paused?: boolean };
    if (typeof body.paused === "boolean") paused = body.paused;
  } catch {
    // default to pause
  }

  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/scheduler/pause", {
      method: "POST",
      body: JSON.stringify({ paused }),
      headers: { "X-Admin-Token": adminToken },
      timeoutMs: 10000,
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Scheduler pause failed";
    return NextResponse.json(envelope(null, false, message), { status: 200 });
  }
}
