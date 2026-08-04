"use client";

import { useMemo } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { TimestampValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
import type { Order, RiskEvent, TradeSignal } from "@/lib/types";

type EventItem = {
  id: string;
  type: string;
  description: string;
  timestamp: string;
  source: string;
};

export default function ActivityPage() {
  const signals = useAsyncData<TradeSignal[]>("/api/signals");
  const orders = useAsyncData<Order[]>("/api/orders");
  const risk = useAsyncData<RiskEvent[]>("/api/risk-events");

  const events = useMemo(() => {
    const items: EventItem[] = [];
    if (signals.status === "success") {
      for (const s of signals.data) {
        items.push({
          id: `s-${s.id}`,
          type: "Signal",
          description: `Strategy signal generated · ${s.symbol} · ${s.direction}`,
          timestamp: s.timestamp,
          source: s.strategy_name,
        });
      }
    }
    if (orders.status === "success") {
      for (const o of orders.data) {
        items.push({
          id: `o-${o.id}`,
          type: "Order",
          description: `Paper order ${o.status.toLowerCase()} · ${o.side} ${o.symbol}`,
          timestamp: o.created_at,
          source: o.strategy_name ?? "Order gateway",
        });
      }
    }
    if (risk.status === "success") {
      for (const r of risk.data) {
        items.push({
          id: `r-${r.id}`,
          type: "Risk",
          description: `Risk check ${r.decision.toLowerCase()} · ${r.reason_code}`,
          timestamp: r.timestamp,
          source: r.strategy_name ?? "Risk engine",
        });
      }
    }
    return items.sort((a, b) => +new Date(b.timestamp) - +new Date(a.timestamp));
  }, [signals, orders, risk]);

  const loading =
    signals.status === "loading" || orders.status === "loading" || risk.status === "loading";
  const errored =
    signals.status === "error" && orders.status === "error" && risk.status === "error";

  return (
    <div className="space-y-4">
      <PageHeader
        title="Activity"
        description="View a chronological record of signals, risk checks, orders and system events."
      />
      <DemoBanner
        demo={signals.meta?.demo || orders.meta?.demo}
        backendError={signals.meta?.backend_error || orders.meta?.backend_error}
      />

      {loading && <LoadingState label="Loading activity…" />}
      {errored && (
        <ErrorState
          title="Unable to load activity"
          message="Project Atlas could not reach activity sources."
          onRetry={() => {
            signals.reload();
            orders.reload();
            risk.reload();
          }}
        />
      )}

      {!loading && !errored &&
        (events.length ? (
          <SectionCard>
            <ol className="space-y-3">
              {events.map((e) => (
                <li key={e.id} className="rounded-control border border-border px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge tone="neutral">{e.type}</Badge>
                    <TimestampValue value={e.timestamp} />
                  </div>
                  <p className="mt-2 text-[14px] text-foreground">{e.description}</p>
                  <p className="mt-1 text-[12px] text-muted">Source · {e.source}</p>
                </li>
              ))}
            </ol>
          </SectionCard>
        ) : (
          <EmptyState title="No activity yet" description="Signals, orders and risk events will appear here." />
        ))}
    </div>
  );
}
