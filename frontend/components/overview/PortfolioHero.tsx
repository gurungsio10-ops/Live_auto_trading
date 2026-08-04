"use client";

import { PaperTradingBadge } from "@/components/ui/Badge";
import { SectionCard } from "@/components/ui/SectionCard";
import { MoneyValue, PercentageValue, PnlValue } from "@/components/values";
import type { EquityPoint, PortfolioSummary } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";

export function PortfolioHero({
  data,
  equity,
  updatedAt,
}: {
  data: PortfolioSummary;
  equity?: EquityPoint[];
  updatedAt?: string | null;
}) {
  const invested = Number(data.equity) - Number(data.cash_balance);
  const dailyPct =
    Number(data.equity) !== 0
      ? (Number(data.daily_pnl) / Math.max(Number(data.equity) - Number(data.daily_pnl), 1)) * 100
      : 0;

  return (
    <SectionCard className="h-full">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[13px] font-medium text-secondary">Paper portfolio</p>
        <div className="flex items-center gap-2">
          <PaperTradingBadge />
          <span className="text-[12px] text-muted">
            {updatedAt ? formatRelativeTime(updatedAt) : "Updated just now"}
          </span>
        </div>
      </div>

      <div className="mt-4">
        <MoneyValue value={data.equity} size="xl" />
        <div className="mt-2 flex flex-wrap items-baseline gap-3">
          <PnlValue value={data.daily_pnl} size="md" />
          <span className="text-[14px] text-secondary">today</span>
          <PercentageValue value={dailyPct} signed />
        </div>
      </div>

      <div className="mt-6 grid grid-cols-3 gap-3 border-t border-border pt-4">
        <div className="min-w-0">
          <p className="text-[12px] text-muted">Available cash</p>
          <MoneyValue value={data.cash_balance} size="sm" className="mt-1 block" />
        </div>
        <div className="min-w-0">
          <p className="text-[12px] text-muted">Invested</p>
          <MoneyValue
            value={Number.isFinite(invested) ? invested : null}
            size="sm"
            className="mt-1 block"
          />
        </div>
        <div className="min-w-0">
          <p className="text-[12px] text-muted">Unrealised P/L</p>
          <PnlValue value={data.unrealized_pnl} size="sm" className="mt-1 block" />
        </div>
      </div>

      <div className="mt-4 rounded-control border border-border bg-surface-raised/50 px-3 py-3 text-[13px] text-secondary">
        {equity && equity.length > 1
          ? `Equity history available (${equity.length} points). Charts appear on the Portfolio page.`
          : "Equity history unavailable"}
      </div>
    </SectionCard>
  );
}
