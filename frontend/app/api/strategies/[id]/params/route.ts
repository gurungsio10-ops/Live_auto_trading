import { NextRequest, NextResponse } from "next/server";
import { adminHeaders, backendFetch, envelope } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const body = (await req.json()) as {
    paper_params: Record<string, string | number | boolean>;
  };
  try {
    const data = await backendFetch(`/strategies/${params.id}/params`, {
      method: "PATCH",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(null, false, err instanceof Error ? err.message : "backend down"),
      { status: 503 },
    );
  }
}
