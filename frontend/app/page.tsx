"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Shield } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { Badge } from "@/components/ui/Badge";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { HeroEquityCard } from "@/components/ops/HeroEquityCard";
import { MetricCard } from "@/components/ops/MetricCard";
import { SystemStatusCard } from "@/components/ops/SystemStatusCard";
import { SignalCard, SignalListHeader } from "@/components/ops/SignalCard";
import { SafetyControls } from "@/components/overview/SafetyControls";
import { MoneyValue, PnlValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
import { deriveRiskScore } from "@/lib/nav";
import { formatRelativeTime } from "@/lib/format";
import type {
  EquityPoint,
  HealthStatus,
  Order,
  PortfolioSummary,
  RiskEvent,
  SettingsView,
  TradeSignal,
} from "@/lib/types";

type SchedulerStatus = {
  enabled?: boolean;
  paused?: boolean;
  status?: string;
  worker_running?: boolean;
};

type SystemHealth = {
  market_data?: { ok?: boolean; label?: string };
  scheduler?: SchedulerStatus;
  kill_switch_enabled?: boolean;
};

export default function OverviewPage() {
  const portfolio = useAsyncData<PortfolioSummary>("/api/portfolio");
  const equity = useAsyncData<EquityPoint[]>("/api/equity-curve");
  const health = useAsyncData<HealthStatus>("/api/health");
  const systemHealth = useAsyncData<SystemHealth | null>("/api/system-health");
  const scheduler = useAsyncData<SchedulerStatus | null>("/api/scheduler/status");
  const signals = useAsyncData<TradeSignal[]>("/api/signals");
  const riskEvents = useAsyncData<RiskEvent[]>("/api/risk-events");
  const orders = useAsyncData<Order[]>("/api/orders");
  const settings = useAsyncData<SettingsView>("/api/settings");

  const [msg, setMsg] = useState<string | null>(null);

  const risk = useMemo(() => {
    if (portfolio.status !== "success") return null;
    return deriveRiskScore({
      kill_switch_enabled: portfolio.data.kill_switch_enabled,
      trading_paused: portfolio.data.trading_paused,
      drawdown: portfolio.data.drawdown,
      maxDrawdown:
        settings.status === "success" ? settings.data.risk_limits.max_drawdown : undefined,
      daily_pnl: portfolio.data.daily_pnl,
      maxDailyLoss:
        settings.status === "success" ? settings.data.risk_limits.max_daily_loss : undefined,
      equity: portfolio.data.equity,
    });
  }, [portfolio, settings]);

  const statusItems = useMemo(() => {
    const backendOk =
      health.status === "success" ? Boolean(health.data.backend_reachable) : null;
    const md = systemHealth.status === "success" ? systemHealth.data?.market_data : undefined;
    const kill =
      portfolio.status === "success"
        ? portfolio.data.kill_switch_enabled
        : systemHealth.status === "success"
          ? systemHealth.data?.kill_switch_enabled
          : null;
    const sched =
      scheduler.status === "success"
        ? scheduler.data
        : systemHealth.status === "success"
          ? systemHealth.data?.scheduler
          : null;

    let schedulerLabel = "Unavailable";
    let schedulerTone: "positive" | "warning" | "neutral" | "negative" = "neutral";
    if (sched) {
      if (sched.paused) {
        schedulerLabel = "Idle";
        schedulerTone = "warning";
      } else if (sched.worker_running || String(sched.status).toLowerCase() === "running") {
        schedulerLabel = "Running";
        schedulerTone = "positive";
      } else if (sched.enabled) {
        schedulerLabel = "Idle";
        schedulerTone = "neutral";
      } else {
        schedulerLabel = "Off";
        schedulerTone = "neutral";
      }
    }

    return [
      {
        key: "backend",
        label: "Backend",
        value: backendOk == null ? "Unknown" : backendOk ? "Connected" : "Disconnected",
        tone: (backendOk == null ? "neutral" : backendOk ? "positive" : "negative") as
          | "neutral"
          | "positive"
          | "negative",
      },
      {
        key: "market",
        label: "Market Data",
        value: md?.label
          ? md.label
          : md?.ok
            ? "Live public data"
            : md
              ? "Degraded"
              : health.meta?.demo
                ? "Demo"
                : "Unavailable",
        tone: (md?.ok ? "positive" : md ? "warning" : "neutral") as
          | "positive"
          | "warning"
          | "neutral",
      },
      {
        key: "kill",
        label: "Kill Switch",
        value: kill == null ? "Unknown" : kill ? "On" : "Off",
        tone: (kill == null ? "neutral" : kill ? "negative" : "positive") as
          | "neutral"
          | "negative"
          | "positive",
      },
      {
        key: "scheduler",
        label: "Scheduler",
        value: schedulerLabel,
        tone: schedulerTone,
      },
    ];
  }, [health, systemHealth, portfolio, scheduler]);

  const activity = useMemo(() => {
    const rows: { id: string; text: string; time: string; tag: string }[] = [];
    if (orders.status === "success") {
      for (const o of orders.data.slice(0, 4)) {
        rows.push({
          id: `o-${o.id}`,
          text: `Paper order ${o.status.toLowerCase()} · ${o.symbol}`,
          time: o.created_at,
          tag: "Fill",
        });
      }
    }
    if (riskEvents.status === "success") {
      for (const r of riskEvents.data.filter((e) => e.decision !== "APPROVED").slice(0, 4)) {
        rows.push({
          id: `r-${r.id}`,
          text: `Risk ${r.decision.toLowerCase()} · ${r.reason_code}`,
          time: r.timestamp,
          tag: "Risk",
        });
      }
    }
    if (signals.status === "success") {
      for (const s of signals.data.slice(0, 2)) {
        rows.push({
          id: `s-${s.id}`,
          text: `Signal ${s.direction} · ${s.symbol}`,
          time: s.timestamp,
          tag: "Signal",
        });
      }
    }
    return rows.sort((a, b) => +new Date(b.time) - +new Date(a.time)).slice(0, 6);
  }, [orders, riskEvents, signals]);

  return (
    <div className="space-y-4 md:space-y-5">
      <div className="hidden md:block">
        <PageHeader
          title="Overview"
          description="Paper portfolio health, system status and recent strategy activity."
        />
      </div>

      <PaperModeBanner />

      <DemoBanner
        demo={portfolio.meta?.demo || health.meta?.demo}
        backendError={portfolio.meta?.backend_error || health.meta?.backend_error}
      />
      {msg ? (
        <p className="text-[13px] text-info" role="status">
          {msg}
        </p>
      ) : null}

      {portfolio.status === "loading" && <LoadingState label="Loading portfolio…" />}
      {portfolio.status === "error" && (
        <ErrorState
          title="Unable to load portfolio"
          message={portfolio.error}
          onRetry={portfolio.reload}
        />
      )}

      {portfolio.status === "success" && (
        <>
          <div className="grid gap-4 lg:grid-cols-12">
            <div className="lg:col-span-8">
              <HeroEquityCard
                portfolio={portfolio.data}
                equity={equity.status === "success" ? equity.data : undefined}
                equityStatus={equity.status}
              />
            </div>
            <div className="hidden lg:col-span-4 lg:block">
              <SafetyControls
                portfolio={portfolio.data}
                onPortfolioChange={portfolio.setData}
                onMessage={setMsg}
                onCycleComplete={() => {
                  void Promise.all([
                    portfolio.reload(),
                    signals.reload(),
                    riskEvents.reload(),
                    orders.reload(),
                    equity.reload(),
                  ]);
                }}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <MetricCard
              label="Available Balance"
              value={<MoneyValue value={portfolio.data.cash_balance} size="md" />}
              hint={
                Number(portfolio.data.equity) > 0
                  ? `${((Number(portfolio.data.cash_balance) / Number(portfolio.data.equity)) * 100).toFixed(2)}% cash`
                  : undefined
              }
            />
            <MetricCard
              label="Unrealised P&L"
              value={<PnlValue value={portfolio.data.unrealized_pnl} size="md" />}
            />
            <MetricCard
              label="Realised P&L"
              value={<PnlValue value={portfolio.data.realized_pnl} size="md" />}
            />
            <MetricCard
              label="Open Positions"
              value={
                <span className="tabular">{portfolio.data.open_position_count}</span>
              }
            />
            <MetricCard
              label="Daily P&L"
              value={<PnlValue value={portfolio.data.daily_pnl} size="md" />}
            />
            <MetricCard
              label="Risk Score"
              value={
                risk ? (
                  <span className="tabular">
                    {risk.score}
                    <span className="text-[13px] font-medium text-muted"> / 100</span>
                  </span>
                ) : (
                  "—"
                )
              }
              hint={
                risk ? (
                  <span className="inline-flex items-center gap-1">
                    <Shield className="h-3.5 w-3.5 text-positive" aria-hidden />
                    {risk.label}
                    <span className="text-muted"> · derived</span>
                  </span>
                ) : (
                  "Unavailable"
                )
              }
            />
          </div>
        </>
      )}

      <SystemStatusCard items={statusItems} />

      <section>
        <SignalListHeader />
        {signals.status === "loading" && <LoadingState label="Loading signals…" />}
        {signals.status === "error" && (
          <ErrorState message={signals.error} onRetry={signals.reload} />
        )}
        {signals.status === "success" &&
          (signals.data.length ? (
            <div className="grid gap-3 md:grid-cols-2">
              {signals.data.slice(0, 4).map((s) => {
                const match =
                  riskEvents.status === "success"
                    ? riskEvents.data.find((r) => r.symbol === s.symbol)
                    : undefined;
                return (
                  <SignalCard
                    key={s.id}
                    signal={s}
                    riskDecision={match?.decision}
                    compact
                  />
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="No recent signals"
              description="Strategy signals will appear here when the backend reports them."
            />
          ))}
      </section>

      <section className="rounded-card border border-border bg-surface p-4 shadow-soft">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-[15px] font-semibold text-foreground">Recent activity</h2>
          <Link
            href="/activity"
            className="min-h-touch text-[13px] font-semibold text-brand hover:underline"
          >
            View all
          </Link>
        </div>
        {activity.length ? (
          <ul className="space-y-2">
            {activity.map((e) => (
              <li key={e.id} className="rounded-control border border-border px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <Badge tone="neutral">{e.tag}</Badge>
                  <span className="text-[12px] text-muted">{formatRelativeTime(e.time)}</span>
                </div>
                <p className="mt-1 text-[13px] text-foreground">{e.text}</p>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No recent activity" description="Fills, risk events and signals will list here." />
        )}
      </section>

      {portfolio.status === "success" ? (
        <div className="lg:hidden">
          <SafetyControls
            portfolio={portfolio.data}
            onPortfolioChange={portfolio.setData}
            onMessage={setMsg}
            onCycleComplete={() => {
              void Promise.all([
                portfolio.reload(),
                signals.reload(),
                riskEvents.reload(),
                orders.reload(),
              ]);
            }}
          />
        </div>
      ) : null}

      {portfolio.status === "success" && risk ? (
        <p className="text-[11px] text-muted">
          Risk score is derived client-side from kill switch, pause, drawdown and daily loss versus
          configured limits — not a backend model score.
        </p>
      ) : null}
    </div>
  );
}
