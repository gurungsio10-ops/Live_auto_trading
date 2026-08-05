import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

/**
 * Enable paper scheduler. Admin token stays server-side.
 * Body must include confirm: "ENABLE_PAPER_SCHEDULER".
 */
export async function POST(request: Request) {
  const adminToken = process.env.ADMIN_API_TOKEN ?? process.env.ATLAS_ADMIN_API_TOKEN;
  if (!adminToken) {
    return NextResponse.json(
      envelope(null, false, "ADMIN_API_TOKEN not configured on Next.js server"),
      { status: 200 },
    );
  }

  let confirm = "ENABLE_PAPER_SCHEDULER";
  try {
    const body = (await request.json()) as { confirm?: string };
    if (body.confirm) confirm = body.confirm;
  } catch {
    // default confirmation for the controlled UI dialog
  }

  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/scheduler/enable", {
      method: "POST",
      body: JSON.stringify({ confirm }),
      headers: { "X-Admin-Token": adminToken },
      timeoutMs: 10000,
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Scheduler enable failed";
    return NextResponse.json(envelope(null, false, message), { status: 200 });
  }
}
