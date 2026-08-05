import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<{
      items: unknown[];
      total?: number;
      limit?: number;
      offset?: number;
    }>("/api/v1/paper/cycles");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Paper cycles unavailable";
    return NextResponse.json(
      envelope({ items: [], total: 0, limit: 50, offset: 0 }, false, message),
      { status: 200 },
    );
  }
}
