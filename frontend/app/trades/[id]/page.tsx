"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { useAsyncData } from "@/lib/use-async-data";
import { formatTs } from "@/lib/format";
import type { ClosedTrade } from "@/lib/analytics";

export default function TradeDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const trade = useAsyncData<ClosedTrade>(
    id ? `/api/analytics/trades/${id}` : "",
  );

  if (!id) return <ErrorState message="Missing trade id" />;
  if (trade.status === "loading") return <LoadingState label="Loading trade…" />;
  if (trade.status === "error") return <ErrorState message={trade.error} />;

  const t = trade.data;
  const rows: [string, string][] = [
    ["Trade ID", t.id],
    ["Strategy", t.strategy_name],
    ["Pair", t.symbol],
    ["Side", t.side],
    ["Entry time", formatTs(t.entry_time)],
    ["Exit time", formatTs(t.exit_time)],
    ["Entry price", t.entry_price],
    ["Exit price", t.exit_price],
    ["Quantity", t.quantity],
    ["Fees", t.fees],
    ["Slippage", t.slippage],
    ["Gross PnL", t.gross_pnl],
    ["Net PnL", t.net_pnl],
    ["ROI %", `${t.roi_pct}%`],
    ["Duration (s)", String(t.duration_seconds)],
    ["Exit reason", t.exit_reason],
    ["Risk score", t.risk_score],
    ["Market regime", t.market_regime],
    ["Paper session", t.paper_session_id],
  ];

  return (
    <div className="min-w-0 space-y-4" data-testid="trade-detail-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl tracking-[0.08em] uppercase">
            Trade detail
          </h1>
          <p className="mt-1 text-xs text-terminal-dim font-mono">{t.id}</p>
        </div>
        <Badge tone="accent">PAPER</Badge>
      </div>

      <Card title="Journal fields">
        <dl className="space-y-3">
          {rows.map(([k, v]) => (
            <div
              key={k}
              className="flex min-h-[40px] flex-col gap-1 border-b border-terminal-border/50 pb-2 sm:flex-row sm:justify-between"
            >
              <dt className="text-xs uppercase tracking-[0.1em] text-terminal-dim">
                {k}
              </dt>
              <dd className="font-mono text-sm text-terminal-text break-all">{v}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Link
        href="/trades"
        className="inline-flex min-h-[44px] items-center text-xs uppercase tracking-[0.1em] text-terminal-accent"
      >
        ← Back to journal
      </Link>
    </div>
  );
}
