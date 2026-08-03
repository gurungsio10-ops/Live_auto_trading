import { NextRequest, NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
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
    let orders = [...demoState.orders];
    if (status) orders = orders.filter((o) => o.status === status);
    if (symbol) {
      const s = symbol.toUpperCase();
      orders = orders.filter((o) => o.symbol.toUpperCase().includes(s));
    }
    if (date) {
      orders = orders.filter((o) => o.created_at.slice(0, 10) === date);
    }
    return NextResponse.json(
      envelope(orders, true, err instanceof Error ? err.message : "backend down"),
    );
  }
}

export async function POST(req: NextRequest) {
  const body = (await req.json()) as OrderTicketPayload;

  try {
    const data = await backendFetch<Order>("/orders", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const now = new Date().toISOString();
    const order: Order = {
      id: `ord_demo_${Date.now().toString(36)}`,
      client_order_id: `paper-${Date.now().toString(36)}`,
      symbol: body.symbol,
      side: body.side,
      order_type: body.order_type,
      quantity: body.quantity,
      filled_quantity: body.order_type === "market" ? body.quantity : "0",
      price: body.price ?? null,
      average_fill_price: body.order_type === "market" ? body.price ?? "65000" : null,
      status: body.order_type === "market" ? "FILLED" : "SUBMITTED",
      strategy_name: body.strategy_name ?? "manual",
      risk_decision: "APPROVED",
      risk_reason_code: "OK",
      created_at: now,
      updated_at: now,
      fees: "0.00",
    };
    demoState.orders = [order, ...demoState.orders];
    return NextResponse.json(
      envelope(order, true, err instanceof Error ? err.message : "backend down"),
    );
  }
}
