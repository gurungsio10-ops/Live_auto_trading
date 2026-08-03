import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export async function GET() {
  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/testnet/status", {
      timeoutMs: 5000,
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Testnet status unavailable";
    return NextResponse.json(envelope(null, true, message), { status: 200 });
  }
}
