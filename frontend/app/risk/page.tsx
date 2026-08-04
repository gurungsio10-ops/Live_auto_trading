"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { MoneyValue, PercentageValue, PnlValue } from "@/components/values";
import { RiskEventLog } from "@/components/RiskEventLog";
import { useAsyncData } from "@/lib/use-async-data";
import { riskFromPortfolio } from "@/lib/status";
import { formatPct } from "@/lib/format";
import type { PortfolioSummary, RiskEvent, SettingsView } from "@/lib/types";

export default function RiskCentrePage() {
  const portfolio = useAsyncData<PortfolioSummary>("/api/portfolio");
  const settings = useAsyncData<SettingsView>("/api/settings");
  const events = useAsyncData<RiskEvent[]>("/api/risk-events");

  const state =
    portfolio.status === "success"
      ? riskFromPortfolio({
          kill_switch_enabled: portfolio.data.kill_switch_enabled,
          trading_paused: portfolio.data.trading_paused,
          drawdown: portfolio.data.drawdown,
          maxDrawdown:
            settings.status === "success" ? settings.data.risk_limits.max_drawdown : undefined,
        })
      : "safe";

  return (
    <div className="space-y-4">
      <PageHeader
        title="Risk Centre"
        description="Monitor trading limits, loss protection and emergency controls."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={settings.meta?.demo} backendError={settings.meta?.backend_error} />

      {(portfolio.status === "loading" || settings.status === "loading") && <LoadingState />}
      {settings.status === "error" && (
        <ErrorState title="Unable to load risk limits" message={settings.error} onRetry={settings.reload} />
      )}

      {portfolio.status === "success" && settings.status === "success" && (
        <>
          <SectionCard title="Overall risk status">
            <div className="flex flex-wrap items-center gap-3">
              <Badge
                tone={state === "safe" ? "positive" : state === "warning" ? "warning" : "negative"}
              >
                {state}
              </Badge>
              <p className="text-[14px] text-secondary">
                {portfolio.data.kill_switch_enabled || portfolio.data.trading_paused
                  ? "New paper orders are currently restricted."
                  : "New paper orders are currently permitted."}
              </p>
            </div>
          </SectionCard>

          <div className="grid gap-4 md:grid-cols-2">
            <RuleCard
              name="Daily loss limit"
              current={<PnlValue value={portfolio.data.daily_pnl} size="sm" />}
              limit={<PercentageValue value={settings.data.risk_limits.max_daily_loss} />}
              explanation="Daily loss is tracked against the configured paper loss limit."
            />
            <RuleCard
              name="Drawdown"
              current={<PercentageValue value={portfolio.data.drawdown} />}
              limit={<PercentageValue value={settings.data.risk_limits.max_drawdown} />}
              explanation="Peak-to-trough drawdown for the paper account."
            />
            <RuleCard
              name="Open positions"
              current={<span className="tabular text-foreground">{portfolio.data.open_position_count}</span>}
              limit={<span className="tabular text-foreground">{settings.data.risk_limits.max_open_positions}</span>}
              explanation="Number of concurrent paper positions versus the configured maximum."
            />
            <RuleCard
              name="Consecutive losses"
              current={<span className="tabular text-foreground">{portfolio.data.consecutive_losses}</span>}
              limit={
                <span className="tabular text-foreground">
                  {settings.data.risk_limits.max_consecutive_losses}
                </span>
              }
              explanation="Tracks consecutive losing paper trades against the configured limit."
            />
            <RuleCard
              name="Position exposure limit"
              current={<span className="text-muted">Not available</span>}
              limit={<PercentageValue value={settings.data.risk_limits.max_position_exposure} />}
              explanation="Configured maximum position exposure. Current usage is not provided by the backend."
            />
            <RuleCard
              name="Kill switch"
              current={
                <span className="text-foreground">
                  {portfolio.data.kill_switch_enabled ? "Active" : "Inactive"}
                </span>
              }
              limit={<span className="text-muted">Emergency control</span>}
              explanation="When active, new paper order submissions are blocked."
            />
          </div>

          <SectionCard title="Allowed symbols" description="Read-only from configuration">
            <div className="flex flex-wrap gap-2">
              {settings.data.supported_symbols.map((s) => (
                <Badge key={s} tone="primary">
                  {s}
                </Badge>
              ))}
            </div>
            <p className="mt-3 text-[12px] text-muted">
              Min order notional {settings.data.risk_limits.min_order_notional} · Max orders/min{" "}
              {settings.data.risk_limits.max_orders_per_minute} · Default leverage{" "}
              {settings.data.risk_limits.default_leverage}x · Daily loss limit{" "}
              {formatPct(settings.data.risk_limits.max_daily_loss)}
            </p>
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

function RuleCard({
  name,
  current,
  limit,
  explanation,
}: {
  name: string;
  current: React.ReactNode;
  limit: React.ReactNode;
  explanation: string;
}) {
  return (
    <SectionCard title={name}>
      <div className="grid grid-cols-2 gap-3 text-[14px]">
        <div>
          <p className="text-[12px] text-muted">Current</p>
          <div className="mt-1">{current}</div>
        </div>
        <div>
          <p className="text-[12px] text-muted">Limit</p>
          <div className="mt-1">{limit}</div>
        </div>
      </div>
      <p className="mt-3 text-[13px] leading-relaxed text-secondary">{explanation}</p>
    </SectionCard>
  );
}
