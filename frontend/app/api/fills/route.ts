/** Proxy GET /api/v1/fills → FastAPI fills. */

import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";

export async function GET() {
  try {
    const data = await backendFetch<{ items: unknown[]; total: number }>("/api/v1/fills");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const fills = (demoState.orders || [])
      .filter((o) => o.status === "FILLED")
      .map((o) => ({
        id: `fill_${o.id}`,
        order_id: o.id,
        symbol: o.symbol,
        side: o.side,
        quantity: o.filled_quantity,
        price: o.average_fill_price || o.price || "0",
        fee: o.fees,
        timestamp: o.updated_at,
        simulated: true,
      }));
    return NextResponse.json(
      envelope(
        { items: fills, total: fills.length },
        true,
        err instanceof Error ? err.message : "backend unavailable",
      ),
    );
  }
}
