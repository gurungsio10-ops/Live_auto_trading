import { NextRequest, NextResponse } from "next/server";
import { adminHeaders, backendFetch, envelope } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  try {
    const data = await backendFetch(`/strategies/${params.id}/stop`, {
      method: "POST",
      headers: adminHeaders(),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(null, false, err instanceof Error ? err.message : "backend down"),
      { status: 503 },
    );
  }
}
