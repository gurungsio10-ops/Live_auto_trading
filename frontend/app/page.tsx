"use client";

import { useMemo, useState } from "react";
import { PortfolioSummary } from "@/components/PortfolioSummary";
import { TradingModeIndicator } from "@/components/TradingModeIndicator";
import { KillSwitchControl } from "@/components/KillSwitchControl";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { PaperModeBanner } from "@/components/brand/PaperModeBanner";
import {
  HealthSummary,
  deriveHealthItems,
} from "@/components/health/HealthSummary";
import {
  SchedulerStatusCard,
  schedulerFromStatus,
} from "@/components/health/SchedulerStatusCard";
import { RiskReasonPanel } from "@/components/health/RiskReasonPanel";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import type {
  EquityPoint,
  HealthStatus,
  PortfolioSummary as PortfolioSummaryType,
  RiskEvent,
  Strategy,
} from "@/lib/types";

export default function OverviewPage() {
  const portfolio = useAsyncData<PortfolioSummaryType>("/api/portfolio");
  const equity = useAsyncData<EquityPoint[]>("/api/equity-curve");
  const health = useAsyncData<HealthStatus>("/api/health");
  const system = useAsyncData<Record<string, unknown> | null>("/api/v1/status");
  const strategies = useAsyncData<Strategy[]>("/api/strategies");
  const riskEvents = useAsyncData<RiskEvent[]>("/api/risk-events");

  const [pausePending, setPausePending] = useState(false);
  const [exportPending, setExportPending] = useState(false);
  const [cyclePending, setCyclePending] = useState(false);
  const [resetPending, setResetPending] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [lastCycle, setLastCycle] = useState<Record<string, unknown> | null>(null);

  const selectedStrategy = useMemo(() => {
    if (strategies.status !== "success") return null;
    return strategies.data.find((s) => s.selected) ?? strategies.data.find((s) => s.running) ?? null;
  }, [strategies]);

  const schedulerView = useMemo(() => {
    const base = schedulerFromStatus(
      system.status === "success" ? system.data ?? undefined : undefined,
    );
    return {
      ...base,
      activeStrategy: base.activeStrategy ?? selectedStrategy?.name ?? null,
      symbol: base.symbol ?? selectedStrategy?.symbols?.[0] ?? null,
      timeframe: base.timeframe ?? selectedStrategy?.timeframe ?? null,
      recentResult:
        base.recentResult ??
        (lastCycle ? String(lastCycle.signal_direction ?? "—") : null),
    };
  }, [system, selectedStrategy, lastCycle]);

  const healthItems = useMemo(() => {
    const h = health.status === "success" ? health.data : null;
    const sys = system.status === "success" ? system.data : null;
    const recon = (sys?.reconciliation as Record<string, unknown> | undefined) ?? {};
    const sched = (sys?.scheduler as Record<string, unknown> | undefined) ?? {};
    const db =
      typeof sys?.database_ok === "boolean"
        ? (sys.database_ok as boolean)
        : typeof (sys?.database as Record<string, unknown> | undefined)?.ok === "boolean"
          ? Boolean((sys?.database as Record<string, unknown>).ok)
          : h?.backend_reachable
            ? true
            : null;

    return deriveHealthItems({
      backendOk: h?.backend_reachable ?? null,
      databaseOk: db,
      redisOk: typeof sys?.redis_ok === "boolean" ? (sys.redis_ok as boolean) : null,
      marketDataOk: typeof sys?.market_data_ok === "boolean" ? (sys.market_data_ok as boolean) : null,
      schedulerEnabled: typeof sched.enabled_by_config === "boolean" ? (sched.enabled_by_config as boolean) : null,
      schedulerRunning: typeof sched.running === "boolean" ? (sched.running as boolean) : null,
      schedulerError: (sched.last_error as string | null | undefined) ?? null,
      engineOk: h?.backend_reachable ?? null,
      reconciliationOk:
        typeof recon.healthy === "boolean"
          ? (recon.healthy as boolean)
          : typeof sys?.reconciliation_healthy === "boolean"
            ? (sys.reconciliation_healthy as boolean)
            : null,
    });
  }, [health, system]);

  const latestRisk =
    riskEvents.status === "success"
      ? riskEvents.data.find((e) => e.decision !== "APPROVED") ?? riskEvents.data[0] ?? null
      : null;

  async function togglePause() {
    if (portfolio.status !== "success") return;
    const next = !portfolio.data.trading_paused;
    const ok = window.confirm(
      next ? "Pause paper trading?" : "Resume paper trading?",
    );
    if (!ok) return;
    setPausePending(true);
    setActionMsg(null);
    try {
      const res = await api.post<PortfolioSummaryType>("/api/trading/pause", {
        paused: next,
      });
      portfolio.setData(res.data);
      setActionMsg(res.data.trading_paused ? "Trading paused" : "Trading resumed");
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Pause failed");
    } finally {
      setPausePending(false);
    }
  }

  async function exportJournal() {
    setExportPending(true);
    setActionMsg(null);
    try {
      const res = await api.get<{ filename: string; content: string; content_type: string }>(
        "/api/journal/export",
      );
      const blob = new Blob([res.data.content], { type: res.data.content_type });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.data.filename;
      a.click();
      URL.revokeObjectURL(url);
      setActionMsg(`Exported ${res.data.filename}`);
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExportPending(false);
    }
  }

  async function runPaperCycle() {
    const ok = window.confirm(
      "Run one paper cycle?\n\nThis simulates a strategy → risk → paper fill path. No live money.",
    );
    if (!ok) return;
    setCyclePending(true);
    setActionMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>("/api/paper/cycle", {});
      if (res.meta?.backend_error) {
        setActionMsg(res.meta.backend_error);
        return;
      }
      setLastCycle(res.data);
      const direction = String(res.data?.signal_direction ?? "hold");
      const order = res.data?.order_id ? ` order=${res.data.order_id}` : "";
      setActionMsg(`Paper cycle: ${direction}${order} (simulated — not live money)`);
      await Promise.all([portfolio.reload(), equity.reload(), riskEvents.reload(), system.reload()]);
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Paper cycle failed");
    } finally {
      setCyclePending(false);
    }
  }

  async function resetPaperAccount() {
    const ok = window.confirm(
      "Reset the PAPER account to the starting balance?\n\nThis clears simulated positions, orders, and session state.",
    );
    if (!ok) return;
    setResetPending(true);
    setActionMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>("/api/paper/reset", {
        confirm: "RESET_PAPER_ACCOUNT",
      });
      if (res.meta?.backend_error) {
        setActionMsg(res.meta.backend_error);
        return;
      }
      setLastCycle(null);
      setActionMsg("Paper account reset (simulated)");
      await Promise.all([portfolio.reload(), equity.reload()]);
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Paper reset failed");
    } finally {
      setResetPending(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="font-display text-[clamp(1.25rem,4vw,1.75rem)] tracking-[0.08em] uppercase text-terminal-text">
            Overview
          </h1>
          <p className="mt-1 text-xs text-terminal-dim">
            Paper status, health, equity, and operational controls.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
          <Button type="button" variant="secondary" disabled={cyclePending} onClick={runPaperCycle}>
            {cyclePending ? "Running…" : "Run paper cycle"}
          </Button>
          <Button
            type="button"
            variant="warn"
            disabled={pausePending || portfolio.status !== "success"}
            onClick={togglePause}
          >
            {pausePending
              ? "…"
              : portfolio.status === "success" && portfolio.data.trading_paused
                ? "Resume"
                : "Pause"}
          </Button>
          <Button type="button" variant="secondary" disabled={exportPending} onClick={exportJournal}>
            {exportPending ? "…" : "Export"}
          </Button>
          <Button type="button" variant="danger" disabled={resetPending} onClick={resetPaperAccount}>
            {resetPending ? "…" : "Reset paper"}
          </Button>
        </div>
      </div>

      {/* 1. PAPER status */}
      {portfolio.status === "success" ? (
        <TradingModeIndicator mode={portfolio.data.trading_mode} />
      ) : (
        <PaperModeBanner />
      )}

      <DemoBanner
        demo={portfolio.meta?.demo || equity.meta?.demo || health.meta?.demo}
        backendError={
          portfolio.meta?.backend_error || equity.meta?.backend_error || health.meta?.backend_error
        }
      />
      {actionMsg && (
        <p className="text-[11px] font-mono text-terminal-accent" role="status">
          {actionMsg}
        </p>
      )}

      {/* 2. System health */}
      {health.status === "loading" && system.status === "loading" ? (
        <LoadingState label="Loading system health…" />
      ) : (
        <HealthSummary items={healthItems} />
      )}

      {/* 3–5 Portfolio equity / daily PnL / exposure */}
      {portfolio.status === "loading" && <LoadingState label="Loading portfolio…" />}
      {portfolio.status === "error" && (
        <ErrorState message={portfolio.error} onRetry={portfolio.reload} />
      )}
      {portfolio.status === "success" && (
        <Card title="Portfolio" subtitle="Equity, cash, and P&L">
          <PortfolioSummary data={portfolio.data} />
        </Card>
      )}

      {/* 6–7 Strategy + Scheduler */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Strategy status" subtitle="Selected paper strategy">
          {strategies.status === "loading" && <LoadingState label="Loading strategies…" />}
          {strategies.status === "error" && (
            <ErrorState message={strategies.error} onRetry={strategies.reload} />
          )}
          {strategies.status === "success" &&
            (selectedStrategy ? (
              <div className="space-y-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-display text-base text-terminal-text">
                    {selectedStrategy.name}
                  </p>
                  <Badge tone={selectedStrategy.running ? "gain" : "neutral"}>
                    {selectedStrategy.running ? "Running" : "Idle"}
                  </Badge>
                  {selectedStrategy.selected ? <Badge tone="accent">Selected</Badge> : null}
                </div>
                <p className="text-[11px] text-terminal-dim">{selectedStrategy.description}</p>
                <p className="font-mono text-[11px] text-terminal-dim">
                  {selectedStrategy.symbols.join(", ")} · {selectedStrategy.timeframe} · v
                  {selectedStrategy.version}
                </p>
              </div>
            ) : (
              <EmptyState title="No strategy selected" description="Choose one under Strategies." />
            ))}
        </Card>
        <SchedulerStatusCard data={schedulerView} />
      </div>

      {/* 8–9 Recent cycle + risk alerts */}
      {lastCycle && (
        <Card title="Latest paper cycle" subtitle="Simulated — not live money">
          <dl className="grid grid-cols-2 gap-3 text-[11px] font-mono">
            <div className="min-w-0">
              <dt className="text-terminal-dim">Signal</dt>
              <dd className="truncate">{String(lastCycle.signal_direction)}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-terminal-dim">Risk</dt>
              <dd className="truncate">{String(lastCycle.risk_decision ?? "—")}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-terminal-dim">Order</dt>
              <dd className="truncate">{String(lastCycle.order_id ?? "none")}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-terminal-dim">Status</dt>
              <dd className="truncate">{String(lastCycle.order_status ?? "—")}</dd>
            </div>
          </dl>
          {lastCycle.risk_reason_code ? (
            <div className="mt-3">
              <RiskReasonPanel
                code={String(lastCycle.risk_reason_code)}
                message={String(lastCycle.signal_reason ?? "")}
                affectedAction="Paper cycle"
              />
            </div>
          ) : null}
          {lastCycle.indicators ? (
            <details className="mt-3 border border-terminal-border p-3">
              <summary className="cursor-pointer text-[11px] uppercase tracking-wide text-terminal-dim">
                Indicator details
              </summary>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-all text-[11px] text-terminal-dim">
                {JSON.stringify(lastCycle.indicators, null, 2)}
              </pre>
            </details>
          ) : null}
        </Card>
      )}

      {latestRisk && latestRisk.decision !== "APPROVED" ? (
        <RiskReasonPanel
          code={latestRisk.reason_code}
          message={latestRisk.message}
          timestamp={latestRisk.timestamp}
          affectedAction={latestRisk.symbol ? `Order on ${latestRisk.symbol}` : "Risk gate"}
        />
      ) : null}

      {/* Kill switch — secondary, confirmed */}
      {portfolio.status === "success" && (
        <KillSwitchControl
          active={portfolio.data.kill_switch_enabled}
          onChanged={(enabled) =>
            portfolio.setData({ ...portfolio.data, kill_switch_enabled: enabled })
          }
        />
      )}

      {/* Charts */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card
          title="Equity curve"
          subtitle="Paper performance (simulated mark-to-market)"
        >
          {equity.status === "loading" && <LoadingState label="Loading equity curve…" />}
          {equity.status === "error" && (
            <ErrorState message={equity.error} onRetry={equity.reload} />
          )}
          {equity.status === "success" &&
            (equity.data.length ? (
              <>
                <p className="mb-2 text-[11px] text-terminal-dim">
                  Paper performance · not a live brokerage statement
                </p>
                <EquityCurveChart data={equity.data} />
              </>
            ) : (
              <EmptyState title="No equity points" />
            ))}
        </Card>
        <Card title="Drawdown" subtitle="Peak-to-trough depth (paper)">
          {equity.status === "loading" && <LoadingState label="Loading drawdown…" />}
          {equity.status === "error" && (
            <ErrorState message={equity.error} onRetry={equity.reload} />
          )}
          {equity.status === "success" &&
            (equity.data.length ? (
              <DrawdownChart data={equity.data} />
            ) : (
              <EmptyState title="No drawdown points" />
            ))}
        </Card>
      </div>
    </div>
  );
}
