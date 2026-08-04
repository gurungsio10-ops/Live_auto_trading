import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError, adminHeaders } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => ({}))) as {
      confirm?: string;
    };
    if (body.confirm !== "CLEAR_RECONCILIATION_HALT") {
      return NextResponse.json(
        envelope(null, false, "confirm must equal CLEAR_RECONCILIATION_HALT"),
        { status: 400 },
      );
    }
    const data = await backendFetch<Record<string, unknown>>(
      "/api/v1/reconciliation/clear-halt",
      {
        method: "POST",
        headers: adminHeaders(),
        timeoutMs: 8000,
      },
    );
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message =
      err instanceof BackendError ? err.message : "Clear halt failed";
    // Fail closed — never invent success
    return NextResponse.json(envelope(null, false, message), { status: 503 });
  }
}
