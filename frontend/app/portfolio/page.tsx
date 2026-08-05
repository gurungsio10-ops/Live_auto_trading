"use client";

import { useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { PositionCard } from "@/components/cards/PositionCard";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { MoneyValue, PnlValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import type { EquityPoint, PortfolioSummary, Position } from "@/lib/types";

export default function PortfolioPage() {
  const portfolio = useAsyncData<PortfolioSummary>("/api/portfolio");
  const equity = useAsyncData<EquityPoint[]>("/api/equity-curve");
  const positions = useAsyncData<Position[]>("/api/positions");
  const [closing, setClosing] = useState<string | null>(null);

  async function closePosition(symbol: string) {
    setClosing(symbol);
    try {
      await api.post("/api/positions/close", { symbol });
      await Promise.all([positions.reload(), portfolio.reload()]);
    } finally {
      setClosing(null);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Portfolio"
        description="Review simulated balance, holdings, open positions and account performance."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={portfolio.meta?.demo} backendError={portfolio.meta?.backend_error} />

      {portfolio.status === "loading" && <LoadingState label="Loading portfolio…" />}
      {portfolio.status === "error" && (
        <ErrorState title="Unable to load portfolio" message={portfolio.error} onRetry={portfolio.reload} />
      )}
      {portfolio.status === "success" && (
        <SectionCard title="Paper balance">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Stat label="Total paper balance" value={<MoneyValue value={portfolio.data.equity} size="lg" />} />
            <Stat label="Available cash" value={<MoneyValue value={portfolio.data.cash_balance} />} />
            <Stat
              label="Asset value"
              value={
                <MoneyValue
                  value={Number(portfolio.data.equity) - Number(portfolio.data.cash_balance)}
                />
              }
            />
            <Stat label="Unrealised P/L" value={<PnlValue value={portfolio.data.unrealized_pnl} />} />
            <Stat label="Realised P/L" value={<PnlValue value={portfolio.data.realized_pnl} />} />
            <Stat label="Daily P/L" value={<PnlValue value={portfolio.data.daily_pnl} />} />
          </div>
        </SectionCard>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        <SectionCard title="Equity curve" description="Paper performance (simulated)">
          {equity.status === "loading" && <LoadingState />}
          {equity.status === "error" && <ErrorState message={equity.error} onRetry={equity.reload} />}
          {equity.status === "success" &&
            (equity.data.length ? (
              <EquityCurveChart data={equity.data} />
            ) : (
              <EmptyState title="Equity history unavailable" />
            ))}
        </SectionCard>
        <SectionCard title="Drawdown" description="Peak-to-trough depth (paper)">
          {equity.status === "success" && equity.data.length ? (
            <DrawdownChart data={equity.data} />
          ) : (
            <EmptyState title="Drawdown history unavailable" />
          )}
        </SectionCard>
      </div>

      <SectionCard title="Open positions">
        {positions.status === "loading" && <LoadingState />}
        {positions.status === "error" && (
          <ErrorState message={positions.error} onRetry={positions.reload} />
        )}
        {positions.status === "success" &&
          (positions.data.length ? (
            <div className="grid gap-3 md:grid-cols-2">
              {positions.data.map((p) => (
                <PositionCard
                  key={`${p.symbol}-${p.opened_at}`}
                  position={p}
                  onClose={closePosition}
                  closing={closing === p.symbol}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No open positions"
              description="The paper account currently has no active positions."
            />
          ))}
      </SectionCard>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0 rounded-control border border-border px-3 py-3">
      <p className="text-[12px] text-muted">{label}</p>
      <div className="mt-1">{value}</div>
    </div>
  );
}
