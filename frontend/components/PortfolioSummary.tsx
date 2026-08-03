"use client";

import type { PortfolioSummary as PortfolioSummaryType } from "@/lib/types";
import { formatMoney, formatPct, pnlTone } from "@/lib/format";

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "gain" | "loss" | "flat";
}) {
  const color =
    tone === "gain"
      ? "text-gain"
      : tone === "loss"
        ? "text-loss"
        : "text-terminal-text";
  return (
    <div className="border border-terminal-border bg-terminal-elevated/50 px-3 py-3">
      <p className="font-display text-[10px] uppercase tracking-[0.14em] text-terminal-dim">
        {label}
      </p>
      <p className={`mt-2 font-mono text-lg tabular-nums ${color}`}>{value}</p>
    </div>
  );
}

export function PortfolioSummary({ data }: { data: PortfolioSummaryType }) {
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
      <Metric label="Balance" value={formatMoney(data.cash_balance)} />
      <Metric label="Equity" value={formatMoney(data.equity)} />
      <Metric
        label="Realized P&L"
        value={formatMoney(data.realized_pnl)}
        tone={pnlTone(data.realized_pnl)}
      />
      <Metric
        label="Unrealized P&L"
        value={formatMoney(data.unrealized_pnl)}
        tone={pnlTone(data.unrealized_pnl)}
      />
      <Metric
        label="Daily P&L"
        value={formatMoney(data.daily_pnl)}
        tone={pnlTone(data.daily_pnl)}
      />
      <Metric
        label="Drawdown"
        value={formatPct(data.drawdown)}
        tone={Number(data.drawdown) > 0 ? "loss" : "flat"}
      />
      <Metric label="Open positions" value={String(data.open_position_count)} />
      <Metric label="Consec. losses" value={String(data.consecutive_losses)} />
    </div>
  );
}
