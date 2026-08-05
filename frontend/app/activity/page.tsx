"use client";

import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAsyncData } from "@/lib/use-async-data";
import { formatMoney, formatQty, formatTs } from "@/lib/format";
import type { RiskEvent, TradeSignal } from "@/lib/types";

type FillRow = {
  id: string;
  order_id: string;
  symbol: string;
  side: string;
  quantity: string;
  price: string;
  fee: string;
  timestamp: string;
  simulated?: boolean;
};

function SectionHeader({
  title,
  href,
  count,
}: {
  title: string;
  href: string;
  count: number;
}) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <h2 className="font-display text-sm uppercase tracking-[0.12em] text-terminal-text">
        {title}
      </h2>
      <Link
        href={href}
        className="inline-flex min-h-[44px] items-center text-[11px] font-mono text-terminal-accent underline-offset-2 hover:underline"
      >
        View all ({count})
      </Link>
    </div>
  );
}

export default function ActivityPage() {
  const fills = useAsyncData<{ items: FillRow[]; total: number }>("/api/fills");
  const signals = useAsyncData<TradeSignal[]>("/api/signals");
  const risk = useAsyncData<RiskEvent[]>("/api/risk-events");

  const loading =
    fills.status === "loading" ||
    signals.status === "loading" ||
    risk.status === "loading";
  const anyError =
    fills.status === "error" || signals.status === "error" || risk.status === "error";

  return (
    <div className="min-w-0 space-y-4" data-testid="activity-page">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase">Activity</h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Recent fills, signals, and risk events — paper journal trail.
        </p>
      </div>

      <DemoBanner
        demo={fills.meta?.demo || signals.meta?.demo || risk.meta?.demo}
        backendError={
          fills.meta?.backend_error ||
          signals.meta?.backend_error ||
          risk.meta?.backend_error
        }
      />

      {loading && <LoadingState label="Loading activity…" />}
      {anyError && !loading && (
        <ErrorState
          message="One or more activity feeds failed to load"
          onRetry={() => {
            void fills.reload();
            void signals.reload();
            void risk.reload();
          }}
        />
      )}

      {fills.status === "success" && (
        <Card title="Recent fills">
          <SectionHeader title="Fills" href="/fills" count={fills.data.total} />
          {!fills.data.items.length ? (
            <EmptyState title="No fills yet" description="Paper fills appear after cycles." />
          ) : (
            <ul className="space-y-2">
              {fills.data.items.slice(0, 8).map((f) => (
                <li
                  key={f.id}
                  className="border border-terminal-border/80 bg-terminal-elevated/30 px-3 py-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-display text-sm text-terminal-accent">
                        {f.symbol}
                      </p>
                      <p className="mt-1 text-[11px] font-mono text-terminal-dim">
                        {formatTs(f.timestamp)}
                      </p>
                    </div>
                    <Badge tone={String(f.side).toUpperCase() === "BUY" ? "gain" : "loss"}>
                      {String(f.side).toUpperCase()}
                    </Badge>
                  </div>
                  <p className="mt-2 text-[11px] font-mono tabular-nums text-terminal-text">
                    {formatQty(f.quantity)} @ {formatMoney(f.price)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {signals.status === "success" && (
        <Card title="Recent signals">
          <SectionHeader title="Signals" href="/signals" count={signals.data.length} />
          {!signals.data.length ? (
            <EmptyState title="No signals" />
          ) : (
            <ul className="space-y-2">
              {signals.data.slice(0, 8).map((s) => (
                <li
                  key={s.id}
                  className="border border-terminal-border/80 bg-terminal-elevated/30 px-3 py-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm text-terminal-text">{s.strategy_name}</p>
                      <p className="mt-1 truncate text-[11px] text-terminal-dim">
                        {s.entry_rationale || s.symbol}
                      </p>
                    </div>
                    <Badge
                      tone={
                        s.direction === "buy"
                          ? "gain"
                          : s.direction === "sell"
                            ? "loss"
                            : "neutral"
                      }
                    >
                      {String(s.direction).toUpperCase()}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {risk.status === "success" && (
        <Card title="Risk events">
          <SectionHeader title="Risk" href="/risk-events" count={risk.data.length} />
          {!risk.data.length ? (
            <EmptyState title="No risk events" />
          ) : (
            <ul className="space-y-2">
              {risk.data.slice(0, 8).map((e) => (
                <li
                  key={e.id}
                  className="border border-terminal-border/80 bg-terminal-elevated/30 px-3 py-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="min-w-0 truncate text-sm text-terminal-text">
                      {e.reason_code}
                    </p>
                    <Badge tone={e.decision === "REJECTED" ? "danger" : "accent"}>
                      {e.decision}
                    </Badge>
                  </div>
                  <p className="mt-1 text-[11px] font-mono text-terminal-dim">
                    {formatTs(e.timestamp)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
