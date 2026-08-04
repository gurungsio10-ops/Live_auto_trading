"use client";

import { useMemo, useState } from "react";
import { OrderTicket } from "@/components/OrderTicket";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { MoneyValue, QuantityValue, TimestampValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
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
  const query = useMemo(
    () => ({
      status: statusFilter === "ALL" ? undefined : statusFilter,
      symbol: symbol || undefined,
    }),
    [statusFilter, symbol],
  );
  const { status, data, error, meta, reload, setData } = useAsyncData<Order[]>("/api/orders", query);
  const field =
    "min-h-touch rounded-control border border-border bg-surface-raised px-3 text-base text-foreground outline-none focus:border-brand sm:text-sm";

  return (
    <div className="space-y-4">
      <PageHeader
        title="Orders"
        description="Review all simulated order requests, fills, rejections and cancellations."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,300px)_1fr]">
        <SectionCard title="Order ticket" description="Paper-only path through risk controls">
          <OrderTicket
            onSubmitted={(order) => {
              if (status === "success") setData([order, ...data]);
              else reload();
            }}
          />
        </SectionCard>

        <SectionCard
          title="Order history"
          actions={
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
              <select
                className={field}
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as OrderStatus | "ALL")}
                aria-label="Status"
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
                aria-label="Symbol"
              />
            </div>
          }
        >
          {status === "loading" && <LoadingState label="Loading orders…" />}
          {status === "error" && <ErrorState message={error} onRetry={reload} />}
          {status === "success" &&
            (data.length === 0 ? (
              <EmptyState
                title="No orders found"
                description="No paper orders match the selected filters."
              />
            ) : (
              <div className="space-y-3">
                {data.map((o) => (
                  <article key={o.id} className="rounded-card border border-border bg-surface-raised/40 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="text-[15px] font-semibold text-foreground">{o.symbol}</p>
                      <div className="flex flex-wrap gap-1">
                        <Badge
                          tone={
                            o.status === "FILLED"
                              ? "positive"
                              : o.status === "REJECTED" || o.status === "FAILED"
                                ? "negative"
                                : "neutral"
                          }
                        >
                          {o.status}
                        </Badge>
                        <Badge tone={o.side === "buy" ? "positive" : "negative"}>{o.side}</Badge>
                        <Badge tone="warning">PAPER</Badge>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-[13px] md:grid-cols-4">
                      <div>
                        <p className="text-muted">Quantity</p>
                        <QuantityValue value={o.quantity} />
                      </div>
                      <div>
                        <p className="text-muted">Requested</p>
                        <MoneyValue value={o.price} size="sm" />
                      </div>
                      <div>
                        <p className="text-muted">Filled</p>
                        <MoneyValue value={o.average_fill_price} size="sm" />
                      </div>
                      <div>
                        <p className="text-muted">Fee</p>
                        <MoneyValue value={o.fees} size="sm" />
                      </div>
                    </div>
                    {(o.status === "REJECTED" || o.status === "FAILED") && o.risk_reason_code ? (
                      <div className="mt-3 rounded-control border border-warning/30 bg-warning-soft px-3 py-2 text-[13px] text-secondary">
                        Rejection reason: {o.risk_reason_code}
                        {o.risk_decision ? ` · ${o.risk_decision}` : ""}
                      </div>
                    ) : null}
                    <p className="mt-3 text-[12px] text-muted">
                      <TimestampValue value={o.created_at} relative />
                    </p>
                  </article>
                ))}
              </div>
            ))}
        </SectionCard>
      </div>
    </div>
  );
}
