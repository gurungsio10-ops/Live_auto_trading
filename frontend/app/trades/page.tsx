"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { useAsyncData } from "@/lib/use-async-data";
import { formatTs } from "@/lib/format";
import type { ClosedTrade } from "@/lib/analytics";

export default function TradesPage() {
  const [q, setQ] = useState("");
  const [side, setSide] = useState("");
  const [strategy, setStrategy] = useState("");
  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (side) params.set("side", side);
    if (strategy.trim()) params.set("strategy_name", strategy.trim());
    params.set("limit", "100");
    const qs = params.toString();
    return `/api/analytics/trades${qs ? `?${qs}` : ""}`;
  }, [q, side, strategy]);

  const trades = useAsyncData<{ trades: ClosedTrade[]; count: number }>(query);

  return (
    <div className="min-w-0 space-y-4" data-testid="trades-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl tracking-[0.08em] uppercase">
            Trade journal
          </h1>
          <p className="mt-1 text-xs text-terminal-dim">
            Closed paper trades with entry/exit, fees, and PnL.
          </p>
        </div>
        <Badge tone="accent">SIMULATED</Badge>
      </div>

      <Card title="Filters">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block text-xs text-terminal-dim">
            Search
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="mt-1 w-full min-h-[44px] border border-terminal-border bg-transparent px-3 font-mono text-sm text-terminal-text"
              placeholder="symbol / strategy / id"
            />
          </label>
          <label className="block text-xs text-terminal-dim">
            Side
            <select
              value={side}
              onChange={(e) => setSide(e.target.value)}
              className="mt-1 w-full min-h-[44px] border border-terminal-border bg-transparent px-3 font-mono text-sm text-terminal-text"
            >
              <option value="">All</option>
              <option value="sell">Sell / exit</option>
              <option value="buy">Buy</option>
            </select>
          </label>
          <label className="block text-xs text-terminal-dim">
            Strategy
            <input
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="mt-1 w-full min-h-[44px] border border-terminal-border bg-transparent px-3 font-mono text-sm text-terminal-text"
              placeholder="ema_crossover"
            />
          </label>
        </div>
      </Card>

      <Card title="History">
        {trades.status === "loading" ? <LoadingState label="Loading trades…" /> : null}
        {trades.status === "error" ? <ErrorState message={trades.error} /> : null}
        {trades.status === "success" ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs font-mono">
              <thead className="text-terminal-dim">
                <tr>
                  <th className="py-2 pr-3">Exit</th>
                  <th className="py-2 pr-3">Pair</th>
                  <th className="py-2 pr-3">Strategy</th>
                  <th className="py-2 pr-3">Net PnL</th>
                  <th className="py-2 pr-3">ROI</th>
                  <th className="py-2">Detail</th>
                </tr>
              </thead>
              <tbody>
                {trades.data.trades.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-4 text-terminal-dim">
                      No closed trades yet. Run paper cycles to populate the journal.
                    </td>
                  </tr>
                ) : (
                  trades.data.trades.map((t) => (
                    <tr key={t.id} className="border-t border-terminal-border/60">
                      <td className="py-3 pr-3 whitespace-nowrap">
                        {formatTs(t.exit_time).slice(0, 16)}
                      </td>
                      <td className="py-3 pr-3">{t.symbol}</td>
                      <td className="py-3 pr-3">{t.strategy_name}</td>
                      <td className="py-3 pr-3">{t.net_pnl}</td>
                      <td className="py-3 pr-3">{t.roi_pct}%</td>
                      <td className="py-3">
                        <Link
                          href={`/trades/${t.id}`}
                          className="inline-flex min-h-[44px] items-center text-terminal-accent"
                        >
                          View
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
