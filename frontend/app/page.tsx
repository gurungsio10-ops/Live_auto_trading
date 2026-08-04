"use client";

import { useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { SectionCard } from "@/components/ui/SectionCard";
import { PaperTradingBadge, Badge } from "@/components/ui/Badge";
import { PortfolioHero } from "@/components/overview/PortfolioHero";
import { EngineStatusCard } from "@/components/overview/EngineStatusCard";
import { SafetyControls } from "@/components/overview/SafetyControls";
import { DecisionCard } from "@/components/cards/DecisionCard";
import { PositionCard } from "@/components/cards/PositionCard";
import { MoneyValue, PercentageValue, PnlValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import { engineFromPortfolio, riskFromPortfolio, systemFromHealth } from "@/lib/status";
import { formatRelativeTime } from "@/lib/format";
import { explainRiskReason } from "@/lib/risk-copy";
import type {
  EquityPoint,
  HealthStatus,
  Order,
  PortfolioSummary,
  Position,
  RiskEvent,
  Strategy,
  TradeSignal,
} from "@/lib/types";

export default function OverviewPage() {
  const portfolio = useAsyncData<PortfolioSummary>("/api/portfolio");
  const equity = useAsyncData<EquityPoint[]>("/api/equity-curve");
  const health = useAsyncData<HealthStatus>("/api/health");
  const strategies = useAsyncData<Strategy[]>("/api/strategies");
  const signals = useAsyncData<TradeSignal[]>("/api/signals");
  const positions = useAsyncData<Position[]>("/api/positions");
  const riskEvents = useAsyncData<RiskEvent[]>("/api/risk-events");
  const orders = useAsyncData<Order[]>("/api/orders");
  const settings = useAsyncData<{ risk_limits: { max_daily_loss: string; max_drawdown: string } }>(
    "/api/settings",
  );

  const [msg, setMsg] = useState<string | null>(null);
  const [lastCycle, setLastCycle] = useState<Record<string, unknown> | null>(null);
  const [closing, setClosing] = useState<string | null>(null);

  const selectedStrategy = useMemo(() => {
    if (strategies.status !== "success") return null;
    return strategies.data.find((s) => s.selected) ?? strategies.data.find((s) => s.running) ?? null;
  }, [strategies]);

  const latestSignal =
    signals.status === "success" && signals.data.length ? signals.data[0] : null;
  const latestRisk =
    riskEvents.status === "success" && riskEvents.data.length ? riskEvents.data[0] : null;

  const system =
    health.status === "success"
      ? systemFromHealth({
          backend_reachable: health.data.backend_reachable,
          demo: health.meta?.demo,
          backend_error: health.meta?.backend_error,
        })
      : systemFromHealth({});

  const engine =
    portfolio.status === "success"
      ? engineFromPortfolio({
          trading_paused: portfolio.data.trading_paused,
          kill_switch_enabled: portfolio.data.kill_switch_enabled,
          strategyRunning: selectedStrategy?.running ?? null,
        })
      : engineFromPortfolio({ strategyRunning: selectedStrategy?.running ?? null });

  const riskState =
    portfolio.status === "success"
      ? riskFromPortfolio({
          kill_switch_enabled: portfolio.data.kill_switch_enabled,
          trading_paused: portfolio.data.trading_paused,
          drawdown: portfolio.data.drawdown,
          maxDrawdown:
            settings.status === "success" ? settings.data.risk_limits.max_drawdown : undefined,
        })
      : "safe";

  async function closePosition(symbol: string) {
    setClosing(symbol);
    try {
      await api.post("/api/positions/close", { symbol });
      await positions.reload();
      await portfolio.reload();
      setMsg(`Closed paper position ${symbol}`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Close failed");
    } finally {
      setClosing(null);
    }
  }

  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-4 md:space-y-5">
      <PageHeader
        title="Overview"
        description="Monitor your paper portfolio, automated strategy and risk controls."
        meta={
          <span className="inline-flex items-center gap-2">
            <PaperTradingBadge />
            <span>Simulated account · no live money</span>
          </span>
        }
      />

      {/* 1 Greeting + 2 Paper badge */}
      <SectionCard>
        <p className="text-[15px] text-secondary">{greet}</p>
        <p className="mt-1 text-xl font-semibold text-foreground">Your paper trading desk</p>
        <div className="mt-3">
          <PaperTradingBadge />
        </div>
      </SectionCard>

      <DemoBanner
        demo={portfolio.meta?.demo || health.meta?.demo}
        backendError={portfolio.meta?.backend_error || health.meta?.backend_error}
      />
      {msg ? (
        <p className="text-[13px] text-info" role="status">
          {msg}
        </p>
      ) : null}

      {/* 3 Portfolio hero + 4 Engine */}
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          {portfolio.status === "loading" && <LoadingState label="Loading portfolio…" />}
          {portfolio.status === "error" && (
            <ErrorState
              title="Unable to load portfolio"
              message={portfolio.error}
              onRetry={portfolio.reload}
            />
          )}
          {portfolio.status === "success" && (
            <PortfolioHero
              data={portfolio.data}
              equity={equity.status === "success" ? equity.data : undefined}
              updatedAt={new Date().toISOString()}
            />
          )}
        </div>
        <div className="lg:col-span-4">
          <EngineStatusCard
            engine={engine}
            system={system}
            strategyName={selectedStrategy?.name}
            lastCycle={
              lastCycle
                ? String(lastCycle.signal_direction ?? "completed")
                : latestSignal
                  ? formatRelativeTime(latestSignal.timestamp)
                  : null
            }
          />
        </div>
      </div>

      {/* 5 Safety + 6 Today's performance */}
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="order-2 lg:order-1 lg:col-span-8">
          <SectionCard title="Today’s performance" description="Paper session metrics currently available">
            {portfolio.status === "success" ? (
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                <Metric label="Daily P/L" value={<PnlValue value={portfolio.data.daily_pnl} size="md" />} />
                <Metric label="Realised P/L" value={<PnlValue value={portfolio.data.realized_pnl} size="md" />} />
                <Metric
                  label="Unrealised P/L"
                  value={<PnlValue value={portfolio.data.unrealized_pnl} size="md" />}
                />
                <Metric
                  label="Open positions"
                  value={<span className="text-[20px] font-semibold tabular text-foreground">{portfolio.data.open_position_count}</span>}
                />
                <Metric
                  label="Consecutive losses"
                  value={<span className="text-[20px] font-semibold tabular text-foreground">{portfolio.data.consecutive_losses}</span>}
                />
                <Metric
                  label="Drawdown"
                  value={<PercentageValue value={portfolio.data.drawdown} />}
                />
              </div>
            ) : (
              <EmptyState title="Performance unavailable" description="Portfolio data is required." />
            )}
          </SectionCard>
        </div>
        <div className="order-1 lg:order-2 lg:col-span-4">
          {portfolio.status === "success" ? (
            <SafetyControls
              portfolio={portfolio.data}
              onPortfolioChange={portfolio.setData}
              onMessage={setMsg}
              onCycleComplete={(data) => {
                setLastCycle(data);
                void Promise.all([portfolio.reload(), signals.reload(), riskEvents.reload(), orders.reload()]);
              }}
            />
          ) : (
            <LoadingState label="Loading controls…" />
          )}
        </div>
      </div>

      {/* 7 Latest decision + 9 Risk summary */}
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          {signals.status === "loading" && <LoadingState label="Loading decisions…" />}
          {signals.status === "error" && (
            <ErrorState message={signals.error} onRetry={signals.reload} />
          )}
          {signals.status === "success" &&
            (latestSignal ? (
              <DecisionCard
                signal={latestSignal}
                riskDecision={
                  (lastCycle?.risk_decision as string | undefined) ??
                  latestRisk?.decision ??
                  null
                }
                riskCode={
                  (lastCycle?.risk_reason_code as string | undefined) ??
                  latestRisk?.reason_code ??
                  null
                }
                execution={
                  lastCycle?.order_id
                    ? `Paper order ${String(lastCycle.order_status ?? "submitted")}`
                    : latestRisk
                      ? `Risk ${latestRisk.decision.toLowerCase()}`
                      : "Not available"
                }
              />
            ) : (
              <EmptyState
                title="No strategy decision"
                description="The selected strategy has not generated a decision yet."
              />
            ))}
        </div>
        <div className="lg:col-span-5">
          <SectionCard title="Risk summary" description="Loss protection and emergency controls">
            {portfolio.status === "success" ? (
              <div className="space-y-3 text-[14px]">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-secondary">Overall risk</span>
                  <Badge
                    tone={
                      riskState === "safe"
                        ? "positive"
                        : riskState === "warning"
                          ? "warning"
                          : "negative"
                    }
                  >
                    {riskState}
                  </Badge>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-secondary">Kill switch</span>
                  <span className="font-medium text-foreground">
                    {portfolio.data.kill_switch_enabled ? "Active" : "Inactive"}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-secondary">Daily P/L</span>
                  <PnlValue value={portfolio.data.daily_pnl} size="sm" />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-secondary">Drawdown</span>
                  <PercentageValue value={portfolio.data.drawdown} />
                </div>
                {latestRisk && latestRisk.decision !== "APPROVED" ? (
                  <div className="rounded-control border border-warning/30 bg-warning-soft p-3 text-[13px] text-secondary">
                    <p className="font-semibold text-foreground">
                      {explainRiskReason(latestRisk.reason_code).title}
                    </p>
                    <p className="mt-1">{explainRiskReason(latestRisk.reason_code).summary}</p>
                  </div>
                ) : (
                  <p className="text-[13px] text-secondary">No active risk blocks reported.</p>
                )}
              </div>
            ) : (
              <EmptyState title="Risk data unavailable" />
            )}
          </SectionCard>
        </div>
      </div>

      {/* 8 Open positions + 10 Recent activity */}
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <SectionCard title="Open positions" description="Up to three active paper positions">
            {positions.status === "loading" && <LoadingState label="Loading positions…" />}
            {positions.status === "error" && (
              <ErrorState message={positions.error} onRetry={positions.reload} />
            )}
            {positions.status === "success" &&
              (positions.data.length ? (
                <div className="space-y-3">
                  {positions.data.slice(0, 3).map((p) => (
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
                  description="The paper account currently has no active market exposure."
                />
              ))}
          </SectionCard>
        </div>
        <div className="lg:col-span-5">
          <SectionCard title="Recent activity" description="Latest genuine paper events">
            {orders.status === "success" || riskEvents.status === "success" || signals.status === "success" ? (
              <ul className="space-y-3">
                {[
                  ...(signals.status === "success"
                    ? signals.data.slice(0, 2).map((s) => ({
                        id: `s-${s.id}`,
                        text: `Strategy signal generated for ${s.symbol}`,
                        time: s.timestamp,
                        tag: "Signal",
                      }))
                    : []),
                  ...(orders.status === "success"
                    ? orders.data.slice(0, 2).map((o) => ({
                        id: `o-${o.id}`,
                        text: `Paper order ${o.status.toLowerCase()} · ${o.symbol}`,
                        time: o.created_at,
                        tag: "Order",
                      }))
                    : []),
                  ...(riskEvents.status === "success"
                    ? riskEvents.data.slice(0, 2).map((r) => ({
                        id: `r-${r.id}`,
                        text: `Risk rule ${r.decision.toLowerCase()} · ${r.reason_code}`,
                        time: r.timestamp,
                        tag: "Risk",
                      }))
                    : []),
                ]
                  .sort((a, b) => +new Date(b.time) - +new Date(a.time))
                  .slice(0, 5)
                  .map((e) => (
                    <li key={e.id} className="rounded-control border border-border px-3 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <Badge tone="neutral">{e.tag}</Badge>
                        <span className="text-[12px] text-muted">{formatRelativeTime(e.time)}</span>
                      </div>
                      <p className="mt-1 text-[13px] text-foreground">{e.text}</p>
                    </li>
                  ))}
              </ul>
            ) : (
              <LoadingState label="Loading activity…" />
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-control border border-border bg-surface-raised/40 px-3 py-3">
      <p className="text-[12px] text-muted">{label}</p>
      <div className="mt-1 min-w-0">{value}</div>
    </div>
  );
}
