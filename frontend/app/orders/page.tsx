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
import { MobileRecordCard, RecordRow } from "@/components/data/MobileRecordCard";
import { MoneyValue, QuantityValue, TimestampValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
import type { Order, OrderStatus } from "@/lib/types";
import { reasonCodeTone } from "@/lib/risk-copy";

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
    "min-h-11 border border-terminal-border bg-terminal-bg px-3 py-2 text-base text-terminal-text outline-none focus:border-terminal-accent font-mono sm:text-xs";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-[clamp(1.25rem,4vw,1.75rem)] tracking-[0.08em] uppercase">
          Trading
        </h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Paper order ticket and history. All fills are simulated.
        </p>
      </div>
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,280px)_1fr]">
        <Card title="Order ticket" subtitle="Paper-only path through risk proxy">
          <OrderTicket
            onSubmitted={(order) => {
              if (status === "success") setData([order, ...data]);
              else reload();
            }
            }
          />
        </Card>

        <Card
          title="Order history"
          actions={
            <div className="flex w-full min-w-0 flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap">
              <select
                className={field}
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as OrderStatus | "ALL")}
                aria-label="Filter by status"
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
                aria-label="Filter by symbol"
              />
              <input
                className={field}
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                aria-label="Filter by date"
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
              <>
                <div className="space-y-2 md:hidden">
                  {data.map((o) => (
                    <MobileRecordCard
                      key={o.id}
                      title={o.symbol}
                      subtitle={<TimestampValue value={o.created_at} compact />}
                      badges={
                        <>
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
                          <Badge tone={o.side === "buy" ? "gain" : "loss"}>{o.side}</Badge>
                        </>
                      }
                      primary={
                        <>
                          <RecordRow
                            label="Qty"
                            value={
                              <>
                                <QuantityValue value={o.filled_quantity} />/
                                <QuantityValue value={o.quantity} />
                              </>
                            }
                          />
                          <RecordRow
                            label="Fill"
                            value={
                              o.average_fill_price ? (
                                <MoneyValue value={o.average_fill_price} compact />
                              ) : o.price ? (
                                <MoneyValue value={o.price} compact />
                              ) : (
                                "—"
                              )
                            }
                          />
                        </>
                      }
                      details={
                        <>
                          <RecordRow label="Type" value={o.order_type} />
                          <RecordRow label="Risk" value={o.risk_decision ?? "—"} />
                          <RecordRow
                            label="Reason"
                            value={
                              o.risk_reason_code ? (
                                <Badge tone={reasonCodeTone(o.risk_reason_code)}>
                                  {o.risk_reason_code}
                                </Badge>
                              ) : (
                                "—"
                              )
                            }
                          />
                          <RecordRow label="Strategy" value={o.strategy_name ?? "—"} />
                        </>
                      }
                    />
                  ))}
                </div>

                <div className="hidden md:block">
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
                        <Td className="whitespace-nowrap text-terminal-dim">
                          <TimestampValue value={o.created_at} />
                        </Td>
                        <Td className="text-terminal-accent">{o.symbol}</Td>
                        <Td className={o.side === "buy" ? "text-gain" : "text-loss"}>
                          {o.side}
                        </Td>
                        <Td>{o.order_type}</Td>
                        <Td>
                          <QuantityValue value={o.filled_quantity} />/
                          <QuantityValue value={o.quantity} />
                        </Td>
                        <Td>
                          {o.average_fill_price ? (
                            <MoneyValue value={o.average_fill_price} />
                          ) : o.price ? (
                            <MoneyValue value={o.price} />
                          ) : (
                            "—"
                          )}
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
                </div>
              </>
            ))}
        </Card>
      </div>
    </div>
  );
}
