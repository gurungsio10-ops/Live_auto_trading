"use client";

import { useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { SignalCard } from "@/components/ops/SignalCard";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { useAsyncData } from "@/lib/use-async-data";
import type { RiskEvent, TradeSignal } from "@/lib/types";

export default function SignalsPage() {
  const signals = useAsyncData<TradeSignal[]>("/api/signals");
  const risk = useAsyncData<RiskEvent[]>("/api/risk-events");
  const [symbol, setSymbol] = useState("");
  const [strategy, setStrategy] = useState("");
  const [direction, setDirection] = useState("ALL");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const filtered = useMemo(() => {
    if (signals.status !== "success") return [];
    return signals.data.filter((s) => {
      if (symbol && !s.symbol.toLowerCase().includes(symbol.toLowerCase())) return false;
      if (strategy && !s.strategy_name.toLowerCase().includes(strategy.toLowerCase())) return false;
      if (direction !== "ALL" && s.direction.toLowerCase() !== direction.toLowerCase()) return false;
      const ts = +new Date(s.timestamp);
      if (from && ts < +new Date(from)) return false;
      if (to && ts > +new Date(to) + 86400000) return false;
      return true;
    });
  }, [signals, symbol, strategy, direction, from, to]);

  const field =
    "min-h-touch w-full rounded-control border border-border bg-surface-raised px-3 text-base text-foreground outline-none focus:border-brand sm:text-sm";

  return (
    <div className="space-y-4">
      <PageHeader
        title="Signals"
        description="Strategy signals reviewed by the central risk engine. No direct execution bypass."
        meta={<PaperTradingBadge />}
      />
      <PaperModeBanner />
      <DemoBanner demo={signals.meta?.demo} backendError={signals.meta?.backend_error} />

      <div className="rounded-card border border-info/30 bg-info-soft px-4 py-3 text-[13px] leading-relaxed text-foreground">
        Signals are informational. Paper orders only execute through the existing risk-controlled
        path — never from an unapproved signal shortcut on this page.
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <input
          className={field}
          placeholder="Symbol"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          aria-label="Filter by symbol"
        />
        <input
          className={field}
          placeholder="Strategy"
          value={strategy}
          onChange={(e) => setStrategy(e.target.value)}
          aria-label="Filter by strategy"
        />
        <select
          className={field}
          value={direction}
          onChange={(e) => setDirection(e.target.value)}
          aria-label="Filter by direction"
        >
          <option value="ALL">All directions</option>
          <option value="buy">BUY</option>
          <option value="sell">SELL</option>
          <option value="hold">NEUTRAL / HOLD</option>
          <option value="exit">EXIT</option>
        </select>
        <input
          className={field}
          type="date"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          aria-label="From date"
        />
        <input
          className={field}
          type="date"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          aria-label="To date"
        />
      </div>

      {signals.status === "loading" && <LoadingState label="Loading signals…" />}
      {signals.status === "error" && (
        <ErrorState title="Unable to load signals" message={signals.error} onRetry={signals.reload} />
      )}
      {signals.status === "success" &&
        (filtered.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {filtered.map((s) => {
              const match =
                risk.status === "success"
                  ? risk.data.find((r) => r.symbol === s.symbol)
                  : undefined;
              return (
                <SignalCard
                  key={s.id}
                  signal={s}
                  riskDecision={match?.decision}
                />
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="No matching signals"
            description="Adjust filters or wait for the selected strategy to produce a decision."
          />
        ))}
    </div>
  );
}
