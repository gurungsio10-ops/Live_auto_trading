import { NextResponse } from "next/server";
import { adminHeaders, backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST() {
  try {
    const data = await backendFetch<Record<string, unknown>>(
      "/api/reconciliation/run",
      {
        method: "POST",
        headers: adminHeaders(),
        timeoutMs: 10000,
      },
    );
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message =
      err instanceof BackendError ? err.message : "Reconciliation failed";
    return NextResponse.json(envelope(null, false, message), { status: 503 });
  }
}
