"use client";

import Link from "next/link";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { PercentageValue, PnlValue } from "@/components/values";
import { RiskEventLog } from "@/components/RiskEventLog";
import { RiskMeter } from "@/components/ops/RiskMeter";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { useAsyncData } from "@/lib/use-async-data";
import { deriveRiskScore } from "@/lib/nav";
import { formatPct } from "@/lib/format";
import type { PortfolioSummary, RiskEvent, SettingsView } from "@/lib/types";

function asPct(value: string | number | undefined): number | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.abs(n) <= 1 ? Math.abs(n) * 100 : Math.abs(n);
}

export default function RiskCentrePage() {
  const portfolio = useAsyncData<PortfolioSummary>("/api/portfolio");
  const settings = useAsyncData<SettingsView>("/api/settings");
  const events = useAsyncData<RiskEvent[]>("/api/risk-events");

  const risk =
    portfolio.status === "success"
      ? deriveRiskScore({
          kill_switch_enabled: portfolio.data.kill_switch_enabled,
          trading_paused: portfolio.data.trading_paused,
          drawdown: portfolio.data.drawdown,
          maxDrawdown:
            settings.status === "success" ? settings.data.risk_limits.max_drawdown : undefined,
          daily_pnl: portfolio.data.daily_pnl,
          maxDailyLoss:
            settings.status === "success" ? settings.data.risk_limits.max_daily_loss : undefined,
          equity: portfolio.data.equity,
        })
      : null;

  const rejected =
    events.status === "success"
      ? events.data.filter((e) => e.decision === "REJECTED" || e.decision === "HALTED").slice(0, 6)
      : [];

  const dailyUsagePct =
    portfolio.status === "success" && settings.status === "success"
      ? (() => {
          const equity = Number(portfolio.data.equity);
          const daily = Number(portfolio.data.daily_pnl);
          const max = asPct(settings.data.risk_limits.max_daily_loss);
          if (max == null || max === 0 || !Number.isFinite(equity) || equity <= 0) return null;
          if (daily >= 0) return 0;
          const used = (Math.abs(daily) / equity) * 100;
          return Math.min(100, (used / max) * 100);
        })()
      : null;

  const drawdownUsage =
    portfolio.status === "success" && settings.status === "success"
      ? (() => {
          const dd = asPct(portfolio.data.drawdown);
          const max = asPct(settings.data.risk_limits.max_drawdown);
          if (dd == null || max == null || max === 0) return null;
          return Math.min(100, (dd / max) * 100);
        })()
      : null;

  const positionUsage =
    portfolio.status === "success" && settings.status === "success"
      ? (() => {
          const max = settings.data.risk_limits.max_open_positions;
          if (!max) return null;
          return Math.min(100, (portfolio.data.open_position_count / max) * 100);
        })()
      : null;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Risk Centre"
        description="Monitor trading limits, loss protection and emergency controls."
        meta={<PaperTradingBadge />}
      />
      <PaperModeBanner />
      <DemoBanner demo={settings.meta?.demo} backendError={settings.meta?.backend_error} />

      {(portfolio.status === "loading" || settings.status === "loading") && <LoadingState />}
      {settings.status === "error" && (
        <ErrorState title="Unable to load risk limits" message={settings.error} onRetry={settings.reload} />
      )}

      {portfolio.status === "success" && settings.status === "success" && (
        <>
          <SectionCard title="Overall risk score" description="Derived from portfolio and configured limits">
            <div className="flex flex-wrap items-end gap-4">
              <p className="text-4xl font-bold tabular text-foreground">
                {risk?.score ?? "—"}
                <span className="text-lg font-medium text-muted"> / 100</span>
              </p>
              <div>
                <Badge
                  tone={
                    (risk?.score ?? 0) >= 80
                      ? "negative"
                      : (risk?.score ?? 0) >= 40
                        ? "warning"
                        : "positive"
                  }
                >
                  {risk?.label ?? "Unavailable"}
                </Badge>
                <p className="mt-1 text-[12px] text-muted">Source: derived (not a backend score)</p>
              </div>
              <Link
                href="/kill-switch"
                className="ml-auto min-h-touch text-[13px] font-semibold text-brand hover:underline"
              >
                Kill switch: {portfolio.data.kill_switch_enabled ? "ON" : "OFF"}
              </Link>
            </div>
          </SectionCard>

          <div className="grid gap-3 md:grid-cols-2">
            <RiskMeter
              label="Daily Loss"
              currentLabel={
                Number(portfolio.data.daily_pnl) < 0
                  ? `${((Math.abs(Number(portfolio.data.daily_pnl)) / Math.max(Number(portfolio.data.equity), 1)) * 100).toFixed(2)}%`
                  : "0.00%"
              }
              limitLabel={formatPct(settings.data.risk_limits.max_daily_loss)}
              pct={dailyUsagePct}
            />
            <RiskMeter
              label="Drawdown"
              currentLabel={
                asPct(portfolio.data.drawdown) != null
                  ? `${asPct(portfolio.data.drawdown)!.toFixed(2)}%`
                  : "—"
              }
              limitLabel={formatPct(settings.data.risk_limits.max_drawdown)}
              pct={drawdownUsage}
            />
            <RiskMeter
              label="Position Size (open count)"
              currentLabel={String(portfolio.data.open_position_count)}
              limitLabel={String(settings.data.risk_limits.max_open_positions)}
              pct={positionUsage}
            />
            <RiskMeter
              label="Total Exposure"
              currentLabel="Unavailable"
              limitLabel={formatPct(settings.data.risk_limits.max_portfolio_exposure)}
              pct={null}
            />
          </div>

          <SectionCard title="Active risk limits">
            <ul className="grid gap-2 text-[13px] sm:grid-cols-2">
              <li className="rounded-control border border-border px-3 py-2">
                Max daily loss: <PercentageValue value={settings.data.risk_limits.max_daily_loss} />
              </li>
              <li className="rounded-control border border-border px-3 py-2">
                Max drawdown: <PercentageValue value={settings.data.risk_limits.max_drawdown} />
              </li>
              <li className="rounded-control border border-border px-3 py-2">
                Max open positions: {settings.data.risk_limits.max_open_positions}
              </li>
              <li className="rounded-control border border-border px-3 py-2">
                Max portfolio exposure:{" "}
                <PercentageValue value={settings.data.risk_limits.max_portfolio_exposure} />
              </li>
              <li className="rounded-control border border-border px-3 py-2">
                Daily P/L: <PnlValue value={portfolio.data.daily_pnl} size="sm" />
              </li>
              <li className="rounded-control border border-border px-3 py-2">
                Kill switch: {portfolio.data.kill_switch_enabled ? "ON" : "OFF"}
              </li>
            </ul>
          </SectionCard>

          <SectionCard title="Latest rejected orders">
            {rejected.length ? (
              <ul className="space-y-2">
                {rejected.map((e) => (
                  <li key={e.id} className="rounded-control border border-border px-3 py-2.5 text-[13px]">
                    <div className="flex items-center justify-between gap-2">
                      <Badge tone="negative">{e.decision}</Badge>
                      <span className="text-muted">{e.symbol ?? "—"}</span>
                    </div>
                    <p className="mt-1 text-foreground">{e.reason_code}</p>
                    <p className="mt-0.5 text-secondary">{e.message}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No recent rejections" />
            )}
          </SectionCard>
        </>
      )}

      <SectionCard title="Recent risk events">
        {events.status === "loading" && <LoadingState />}
        {events.status === "error" && <ErrorState message={events.error} onRetry={events.reload} />}
        {events.status === "success" &&
          (events.data.length ? (
            <RiskEventLog events={events.data} />
          ) : (
            <EmptyState title="No risk events" description="No recent risk rules have been triggered." />
          ))}
      </SectionCard>
    </div>
  );
}
