import { NextRequest, NextResponse } from "next/server";
import { adminHeaders, backendFetch, envelope } from "@/lib/backend";
import type { Order, OrderTicketPayload } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const status = searchParams.get("status");
  const symbol = searchParams.get("symbol");
  const date = searchParams.get("date");
  const qs = new URLSearchParams();
  if (status) qs.set("status", status);
  if (symbol) qs.set("symbol", symbol);
  if (date) qs.set("date", date);
  const path = `/orders${qs.toString() ? `?${qs}` : ""}`;

  try {
    const data = await backendFetch<Order[]>(path);
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope([], false, err instanceof Error ? err.message : "backend down"),
      { status: 503 },
    );
  }
}

export async function POST(req: NextRequest) {
  const body = (await req.json()) as OrderTicketPayload;

  try {
    const data = await backendFetch<Order>("/orders", {
      method: "POST",
      headers: adminHeaders(),
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    // Fail closed — never invent APPROVED/FILLED paper orders offline.
    return NextResponse.json(
      envelope(
        null,
        false,
        err instanceof Error ? err.message : "backend down — order not submitted",
      ),
      { status: 503 },
    );
  }
}
