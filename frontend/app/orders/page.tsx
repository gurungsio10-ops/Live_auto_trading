"use client";

import { useMemo, useState } from "react";
import { OrderTicket } from "@/components/OrderTicket";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, Td } from "@/components/ui/Table";
import { useAsyncData } from "@/lib/use-async-data";
import { formatMoney, formatQty, formatTs } from "@/lib/format";
import type { Order, OrderStatus } from "@/lib/types";

const statuses: Array<OrderStatus | "ALL"> = [
  "ALL",
  "CREATED",
  "RISK_PENDING",
  "APPROVED",
  "SUBMITTED",
  "PARTIALLY_FILLED",
  "FILLED",
  "REJECTED",
  "CANCELLED",
  "EXPIRED",
  "FAILED",
];

export default function OrdersPage() {
  const [statusFilter, setStatusFilter] = useState<OrderStatus | "ALL">("ALL");
  const [symbol, setSymbol] = useState("");
  const [date, setDate] = useState("");

  const query = useMemo(
    () => ({
      status: statusFilter === "ALL" ? undefined : statusFilter,
      symbol: symbol || undefined,
      date: date || undefined,
    }),
    [statusFilter, symbol, date],
  );

  const { status, data, error, meta, reload, setData } = useAsyncData<Order[]>(
    "/api/orders",
    query,
  );

  const field =
    "border border-terminal-border bg-terminal-bg px-2 py-1.5 text-xs text-terminal-text outline-none focus:border-terminal-accent font-mono";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase">Orders</h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Filter by status, symbol, and date. Submit paper tickets via proxy.
        </p>
      </div>
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />

      <div className="grid gap-4 xl:grid-cols-[280px_1fr]">
        <Card title="Order ticket" subtitle="Paper-only path through risk proxy">
          <OrderTicket
            onSubmitted={(order) => {
              if (status === "success") setData([order, ...data]);
              else reload();
            }}
          />
        </Card>

        <Card
          title="Order book / history"
          actions={
            <div className="flex flex-wrap gap-2">
              <select
                className={field}
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as OrderStatus | "ALL")}
              >
                {statuses.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <input
                className={field}
                placeholder="Symbol"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
              />
              <input
                className={field}
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
          }
        >
          {status === "loading" && <LoadingState label="Loading orders…" />}
          {status === "error" && <ErrorState message={error} onRetry={reload} />}
          {status === "success" &&
            (data.length === 0 ? (
              <EmptyState title="No orders match" description="Adjust filters or submit a ticket." />
            ) : (
              <Table
                headers={[
                  "Time",
                  "Symbol",
                  "Side",
                  "Type",
                  "Qty",
                  "Fill px",
                  "Status",
                  "Risk",
                  "Strategy",
                ]}
              >
                {data.map((o) => (
                  <tr key={o.id} className="hover:bg-terminal-muted/40">
                    <Td className="text-terminal-dim whitespace-nowrap">
                      {formatTs(o.created_at)}
                    </Td>
                    <Td className="text-terminal-accent">{o.symbol}</Td>
                    <Td className={o.side === "buy" ? "text-gain" : "text-loss"}>
                      {o.side}
                    </Td>
                    <Td>{o.order_type}</Td>
                    <Td>
                      {formatQty(o.filled_quantity)}/{formatQty(o.quantity)}
                    </Td>
                    <Td>
                      {o.average_fill_price
                        ? formatMoney(o.average_fill_price)
                        : o.price
                          ? formatMoney(o.price)
                          : "—"}
                    </Td>
                    <Td mono={false}>
                      <Badge
                        tone={
                          o.status === "FILLED"
                            ? "gain"
                            : o.status === "REJECTED" || o.status === "FAILED"
                              ? "loss"
                              : "neutral"
                        }
                      >
                        {o.status}
                      </Badge>
                    </Td>
                    <Td className="text-[10px]">
                      {o.risk_decision ?? "—"}
                      {o.risk_reason_code ? ` · ${o.risk_reason_code}` : ""}
                    </Td>
                    <Td>{o.strategy_name ?? "—"}</Td>
                  </tr>
                ))}
              </Table>
            ))}
        </Card>
      </div>
    </div>
  );
}
