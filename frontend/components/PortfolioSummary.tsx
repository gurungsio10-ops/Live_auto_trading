"use client";

import type { PortfolioSummary as PortfolioSummaryType } from "@/lib/types";
import { MoneyValue, PercentageValue, PnlValue } from "@/components/values";

function Metric({
  label,
  children,
  emphasize = false,
}: {
  label: string;
  children: React.ReactNode;
  emphasize?: boolean;
}) {
  return (
    <div
      className={[
        "min-w-0 border border-terminal-border bg-terminal-elevated/50 px-3 py-3",
        emphasize ? "col-span-2 sm:col-span-1" : "",
      ].join(" ")}
    >
      <p className="font-display text-[10px] uppercase tracking-[0.14em] text-terminal-dim">
        {label}
      </p>
      <div className="mt-2 min-w-0 overflow-hidden">{children}</div>
    </div>
  );
}

export function PortfolioSummary({ data }: { data: PortfolioSummaryType }) {
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-4 2xl:grid-cols-8">
      <Metric label="Available" emphasize>
        <MoneyValue value={data.cash_balance} size="lg" compact />
      </Metric>
      <Metric label="Equity" emphasize>
        <MoneyValue value={data.equity} size="lg" compact />
      </Metric>
      <Metric label="Daily P&L">
        <PnlValue value={data.daily_pnl} size="lg" compact />
      </Metric>
      <Metric label="Unrealized">
        <PnlValue value={data.unrealized_pnl} size="md" compact />
      </Metric>
      <Metric label="Realized">
        <PnlValue value={data.realized_pnl} size="md" compact />
      </Metric>
      <Metric label="Drawdown">
        <PercentageValue
          value={data.drawdown}
          size="md"
          className={Number(data.drawdown) > 0 ? "text-loss" : "text-terminal-text"}
        />
      </Metric>
      <Metric label="Open positions">
        <span className="font-mono text-lg tabular-nums text-terminal-text">
          {data.open_position_count}
        </span>
      </Metric>
      <Metric label="Consec. losses">
        <span className="font-mono text-lg tabular-nums text-terminal-text">
          {data.consecutive_losses}
        </span>
      </Metric>
    </div>
  );
}
