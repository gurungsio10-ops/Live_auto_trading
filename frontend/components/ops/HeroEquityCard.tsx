"use client";

import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { MoneyValue, PercentageValue, PnlValue } from "@/components/values";
import type { EquityPoint, PortfolioSummary } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";

const EquityCurveChart = dynamic(
  () => import("@/components/charts/EquityCurveChart").then((m) => m.EquityCurveChart),
  { ssr: false, loading: () => <div className="h-36 animate-pulse rounded-control bg-surface-hover" /> },
);

const TIMEFRAMES = [
  { id: "1D", days: 1 },
  { id: "1W", days: 7 },
  { id: "1M", days: 30 },
  { id: "3M", days: 90 },
  { id: "1Y", days: 365 },
  { id: "ALL", days: null },
] as const;

type Tf = (typeof TIMEFRAMES)[number]["id"];

function filterEquity(data: EquityPoint[] | undefined, tf: Tf): EquityPoint[] {
  if (!data?.length) return [];
  const days = TIMEFRAMES.find((t) => t.id === tf)?.days;
  if (days == null) return data;
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  const filtered = data.filter((p) => +new Date(p.time) >= cutoff);
  return filtered.length >= 2 ? filtered : data.slice(-Math.min(data.length, 2));
}

export function HeroEquityCard({
  portfolio,
  equity,
  equityStatus,
}: {
  portfolio: PortfolioSummary;
  equity?: EquityPoint[];
  equityStatus: "loading" | "success" | "error" | "idle";
}) {
  const [tf, setTf] = useState<Tf>("1D");
  const points = useMemo(() => filterEquity(equity, tf), [equity, tf]);
  const equityNum = Number(portfolio.equity);
  const daily = Number(portfolio.daily_pnl);
  const base = equityNum - daily;
  const dailyPct = base !== 0 && Number.isFinite(base) ? (daily / Math.abs(base)) * 100 : null;

  return (
    <section className="rounded-card border border-border bg-surface p-4 shadow-soft md:p-5">
      <p className="text-[12px] font-semibold uppercase tracking-wide text-muted">Total Equity</p>
      <div className="mt-1">
        <MoneyValue value={portfolio.equity} size="xl" />
      </div>
      <div className="mt-2 flex flex-wrap items-baseline gap-3">
        <PnlValue value={portfolio.daily_pnl} size="md" />
        {dailyPct != null ? (
          <PercentageValue value={dailyPct} signed />
        ) : (
          <span className="text-[13px] text-muted">—</span>
        )}
        <span className="text-[12px] text-muted">daily change</span>
      </div>

      <div className="mt-4">
        {equityStatus === "loading" ? (
          <div className="h-36 animate-pulse rounded-control bg-surface-hover" aria-busy />
        ) : equityStatus === "error" || !points.length ? (
          <EmptyState
            title="Equity chart unavailable"
            description="No fabricated chart is shown when history is missing."
          />
        ) : (
          <div className="h-36 sm:h-44 [&_.h-56]:!h-36 [&_.sm\:h-72]:!h-44">
            <EquityCurveChart data={points} />
          </div>
        )}
      </div>

      <div
        className="mt-3 flex gap-1 overflow-x-auto pb-1"
        role="tablist"
        aria-label="Equity timeframe"
      >
        {TIMEFRAMES.map((t) => {
          const active = tf === t.id;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTf(t.id)}
              className={[
                "min-h-9 shrink-0 rounded-control px-3 text-[12px] font-semibold transition",
                active
                  ? "bg-primary text-white"
                  : "bg-surface-raised text-secondary hover:text-foreground",
              ].join(" ")}
            >
              {t.id}
            </button>
          );
        })}
      </div>
    </section>
  );
}
