import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/brain");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Atlas Brain unavailable";
    return NextResponse.json(envelope(null, false, message), { status: 200 });
  }
}
