import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/analytics/paper");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Paper analytics unavailable";
    return NextResponse.json(envelope(null, false, message), { status: 200 });
  }
}
