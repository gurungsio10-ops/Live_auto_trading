import { NextRequest, NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  try {
    const limit = req.nextUrl.searchParams.get("limit") ?? "50";
    const data = await backendFetch<Record<string, unknown>>(`/api/v1/decisions?limit=${limit}`);
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Decision feed unavailable";
    return NextResponse.json(envelope({ items: [], total: 0 }, false, message), { status: 200 });
  }
}
