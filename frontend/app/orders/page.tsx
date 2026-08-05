"use client";

import { useMemo, useState } from "react";
import { OrderTicket } from "@/components/OrderTicket";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { OrderCard } from "@/components/ops/OrderCard";
import { SegmentTabs } from "@/components/ops/SegmentTabs";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { useAsyncData } from "@/lib/use-async-data";
import type { Order, OrderStatus } from "@/lib/types";

type Tab = "open" | "history" | "cancelled";

const OPEN: OrderStatus[] = [
  "CREATED",
  "RISK_PENDING",
  "APPROVED",
  "SUBMITTED",
  "PARTIALLY_FILLED",
];
const CANCELLED: OrderStatus[] = ["CANCELLED", "EXPIRED"];

export default function OrdersPage() {
  const [tab, setTab] = useState<Tab>("open");
  const [symbol, setSymbol] = useState("");
  const { status, data, error, meta, reload, setData } = useAsyncData<Order[]>("/api/orders");

  const filtered = useMemo(() => {
    if (status !== "success") return [];
    return data.filter((o) => {
      if (symbol && !o.symbol.toLowerCase().includes(symbol.toLowerCase())) return false;
      if (tab === "open") return OPEN.includes(o.status);
      if (tab === "cancelled") return CANCELLED.includes(o.status);
      return !OPEN.includes(o.status) && !CANCELLED.includes(o.status);
    });
  }, [status, data, tab, symbol]);

  const counts = useMemo(() => {
    if (status !== "success") return { open: 0, history: 0, cancelled: 0 };
    return {
      open: data.filter((o) => OPEN.includes(o.status)).length,
      history: data.filter((o) => !OPEN.includes(o.status) && !CANCELLED.includes(o.status)).length,
      cancelled: data.filter((o) => CANCELLED.includes(o.status)).length,
    };
  }, [status, data]);

  const field =
    "min-h-touch rounded-control border border-border bg-surface-raised px-3 text-base text-foreground outline-none focus:border-brand sm:text-sm";

  return (
    <div className="space-y-4">
      <PageHeader
        title="Orders"
        description="Review simulated order requests, fills, rejections and cancellations."
        meta={<PaperTradingBadge />}
      />
      <PaperModeBanner />
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

        <div className="space-y-3">
          <SegmentTabs
            ariaLabel="Order tabs"
            value={tab}
            onChange={setTab}
            tabs={[
              { id: "open", label: "Open", count: counts.open },
              { id: "history", label: "History", count: counts.history },
              { id: "cancelled", label: "Cancelled", count: counts.cancelled },
            ]}
          />
          <input
            className={`w-full ${field}`}
            placeholder="Filter by symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            aria-label="Symbol filter"
          />

          {status === "loading" && <LoadingState label="Loading orders…" />}
          {status === "error" && <ErrorState message={error} onRetry={reload} />}
          {status === "success" &&
            (filtered.length === 0 ? (
              <EmptyState
                title="No orders found"
                description="No paper orders match the selected tab and filters."
              />
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {filtered.map((o) => (
                  <OrderCard key={o.id} order={o} />
                ))}
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
