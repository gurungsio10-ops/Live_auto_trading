import { NextResponse } from "next/server";
import { backendFetch, envelope, BackendError } from "@/lib/backend";

export async function POST(request: Request) {
  const adminToken = process.env.ADMIN_API_TOKEN ?? process.env.ATLAS_ADMIN_API_TOKEN;
  if (!adminToken) {
    return NextResponse.json(
      envelope(null, true, "ADMIN_API_TOKEN not configured on Next.js server"),
      { status: 200 },
    );
  }
  let confirm = "RESET_PAPER_ACCOUNT";
  try {
    const body = (await request.json()) as { confirm?: string };
    if (body.confirm) confirm = body.confirm;
  } catch {
    // default confirmation for the controlled UI button
  }
  try {
    const data = await backendFetch<Record<string, unknown>>("/api/v1/paper/reset", {
      method: "POST",
      body: JSON.stringify({ confirm }),
      headers: { "X-Admin-Token": adminToken },
      timeoutMs: 10000,
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const message = err instanceof BackendError ? err.message : "Paper reset failed";
    return NextResponse.json(envelope(null, true, message), { status: 200 });
  }
}
