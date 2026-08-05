"use client";

import type { PortfolioSummary as PortfolioSummaryType } from "@/lib/types";
import {
  formatInt,
  formatMoney,
  formatMoneyExact,
  formatPct,
  moneyTextClass,
  pnlTone,
} from "@/lib/format";

function Metric({
  label,
  value,
  title,
  tone,
}: {
  label: string;
  value: string;
  title?: string;
  tone?: "gain" | "loss" | "flat";
}) {
  const color =
    tone === "gain"
      ? "text-gain"
      : tone === "loss"
        ? "text-loss"
        : "text-terminal-text";
  return (
    <div className="min-w-0 overflow-hidden border border-terminal-border bg-terminal-elevated/50 px-3 py-3">
      <p className="truncate font-display text-[10px] uppercase tracking-[0.14em] text-terminal-dim">
        {label}
      </p>
      <p
        title={title ?? value}
        className={[
          "mt-2 font-mono tabular-nums whitespace-nowrap overflow-hidden text-ellipsis",
          moneyTextClass(value),
          color,
        ].join(" ")}
      >
        {value}
      </p>
    </div>
  );
}

export function PortfolioSummary({ data }: { data: PortfolioSummaryType }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4 2xl:grid-cols-8">
      <Metric
        label="Available"
        value={formatMoney(data.cash_balance)}
        title={formatMoneyExact(data.cash_balance)}
      />
      <Metric
        label="Equity"
        value={formatMoney(data.equity)}
        title={formatMoneyExact(data.equity)}
      />
      <Metric
        label="Realized P&L"
        value={formatMoney(data.realized_pnl)}
        title={formatMoneyExact(data.realized_pnl)}
        tone={pnlTone(data.realized_pnl)}
      />
      <Metric
        label="Unrealized P&L"
        value={formatMoney(data.unrealized_pnl)}
        title={formatMoneyExact(data.unrealized_pnl)}
        tone={pnlTone(data.unrealized_pnl)}
      />
      <Metric
        label="Daily P&L"
        value={formatMoney(data.daily_pnl)}
        title={formatMoneyExact(data.daily_pnl)}
        tone={pnlTone(data.daily_pnl)}
      />
      <Metric
        label="Drawdown"
        value={formatPct(data.drawdown)}
        tone={Number(data.drawdown) > 0 ? "loss" : "flat"}
      />
      <Metric label="Open positions" value={formatInt(data.open_position_count)} />
      <Metric label="Consec. losses" value={formatInt(data.consecutive_losses)} />
    </div>
  );
}
