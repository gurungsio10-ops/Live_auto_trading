"use client";

import { useState } from "react";
import { PortfolioSummary } from "@/components/PortfolioSummary";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import { TradingModeIndicator } from "@/components/TradingModeIndicator";
import { KillSwitchControl } from "@/components/KillSwitchControl";
import { SchedulerControl } from "@/components/SchedulerControl";
import { OpsStatusStrip } from "@/components/OpsStatusStrip";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import { formatTs } from "@/lib/format";
import type {
  EquityPoint,
  PortfolioSummary as PortfolioSummaryType,
  SystemStatusPayload,
} from "@/lib/types";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export default function OverviewPage() {
  const portfolio = useAsyncData<PortfolioSummaryType>("/api/portfolio");
  const equity = useAsyncData<EquityPoint[]>("/api/equity-curve");
  const system = useAsyncData<SystemStatusPayload>("/api/system/status");
  const [pausePending, setPausePending] = useState(false);
  const [exportPending, setExportPending] = useState(false);
  const [cyclePending, setCyclePending] = useState(false);
  const [resetPending, setResetPending] = useState(false);
  const [reconPending, setReconPending] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionTone, setActionTone] = useState<"ok" | "err">("ok");
  const [lastCycle, setLastCycle] = useState<Record<string, unknown> | null>(null);

  async function togglePause() {
    if (portfolio.status !== "success") return;
    setPausePending(true);
    setActionMsg(null);
    try {
      const res = await api.post<PortfolioSummaryType>("/api/trading/pause", {
        paused: !portfolio.data.trading_paused,
      });
      portfolio.setData(res.data);
      setActionTone("ok");
      setActionMsg(res.data.trading_paused ? "Trading paused" : "Trading resumed");
    } catch (err) {
      setActionTone("err");
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
      setActionTone("ok");
      setActionMsg(`Exported ${res.data.filename}`);
    } catch (err) {
      setActionTone("err");
      setActionMsg(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExportPending(false);
    }
  }

  async function runPaperCycle() {
    setCyclePending(true);
    setActionMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>("/api/paper/cycle", {});
      if (res.meta?.backend_error) {
        setActionTone("err");
        setActionMsg(res.meta.backend_error);
        return;
      }
      setLastCycle(res.data);
      const direction = String(res.data?.signal_direction ?? "hold");
      const order = res.data?.order_id ? ` order=${String(res.data.order_id).slice(0, 12)}` : "";
      setActionTone("ok");
      setActionMsg(`Paper cycle: ${direction}${order} (simulated — not live money)`);
      await Promise.all([portfolio.reload(), equity.reload(), system.reload()]);
    } catch (err) {
      setActionTone("err");
      setActionMsg(err instanceof Error ? err.message : "Paper cycle failed");
    } finally {
      setCyclePending(false);
    }
  }

  async function runReconciliation() {
    setReconPending(true);
    setActionMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>("/api/reconciliation/run", {});
      if (res.meta?.backend_error) {
        setActionTone("err");
        setActionMsg(res.meta.backend_error);
        return;
      }
      const healthy = Boolean(res.data?.healthy);
      setActionTone(healthy ? "ok" : "err");
      setActionMsg(
        healthy
          ? "Reconciliation OK"
          : `Reconciliation HALT: ${String(res.data?.detail ?? "mismatch")}`,
      );
      await system.reload();
    } catch (err) {
      setActionTone("err");
      setActionMsg(err instanceof Error ? err.message : "Reconciliation failed");
    } finally {
      setReconPending(false);
    }
  }

  async function resetPaperAccount() {
    const ok = window.confirm(
      "Reset the PAPER account to the starting balance?\n\nThis clears simulated positions, orders, and session state.\nType confirmation is enforced server-side.",
    );
    if (!ok) return;
    setResetPending(true);
    setActionMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>("/api/paper/reset", {
        confirm: "RESET_PAPER_ACCOUNT",
      });
      if (res.meta?.backend_error) {
        setActionTone("err");
        setActionMsg(res.meta.backend_error);
        return;
      }
      setLastCycle(null);
      setActionTone("ok");
      setActionMsg("Paper account reset (simulated)");
      await Promise.all([portfolio.reload(), equity.reload(), system.reload()]);
    } catch (err) {
      setActionTone("err");
      setActionMsg(err instanceof Error ? err.message : "Paper reset failed");
    } finally {
      setResetPending(false);
    }
  }

  const indicators =
    lastCycle && typeof lastCycle.indicators === "object" && lastCycle.indicators
      ? (lastCycle.indicators as Record<string, unknown>)
      : null;

  const health =
    system.status === "success" ? asRecord(system.data.health) : {};
  const metrics =
    system.status === "success" ? asRecord(system.data.metrics) : {};
  const scheduler = asRecord(health.scheduler ?? metrics.scheduler);
  const schedulerRunning = scheduler.running === true;
  const backendConnected = system.status === "success" && portfolio.status === "success";
  const backendLoading =
    system.status === "loading" || portfolio.status === "loading";

  return (
    <div className="min-w-0 space-y-5" data-testid="home-overview">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-2xl tracking-[0.08em] uppercase text-terminal-text">
            Home
          </h1>
          <p className="mt-1 text-xs text-terminal-dim">
            Portfolio, risk gates, scheduler, and equity — paper only.
          </p>
        </div>
        <div className="flex max-w-full flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            className="min-h-[44px]"
            disabled={cyclePending}
            onClick={runPaperCycle}
          >
            {cyclePending ? "Running…" : "Run one paper cycle"}
          </Button>
          <Button
            type="button"
            variant="warn"
            className="min-h-[44px]"
            disabled={pausePending || portfolio.status !== "success"}
            onClick={togglePause}
          >
            {pausePending
              ? "…"
              : portfolio.status === "success" && portfolio.data.trading_paused
                ? "Resume trading"
                : "Pause trading"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="min-h-[44px]"
            disabled={exportPending}
            onClick={exportJournal}
          >
            {exportPending ? "Exporting…" : "Export journal"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="min-h-[44px]"
            disabled={reconPending}
            onClick={runReconciliation}
          >
            {reconPending ? "Reconciling…" : "Run reconciliation"}
          </Button>
          <Button
            type="button"
            variant="danger"
            className="min-h-[44px]"
            disabled={resetPending}
            onClick={resetPaperAccount}
          >
            {resetPending ? "Resetting…" : "Reset paper account"}
          </Button>
        </div>
      </div>

      <DemoBanner
        demo={portfolio.meta?.demo || equity.meta?.demo}
        backendError={portfolio.meta?.backend_error || equity.meta?.backend_error}
      />

      {/* Mobile-priority strip: mode + connectivity + controls status */}
      <OpsStatusStrip
        runtimeMode={
          portfolio.status === "success"
            ? (portfolio.data as { runtime_mode?: string }).runtime_mode
            : undefined
        }
        tradingMode={
          portfolio.status === "success" ? portfolio.data.trading_mode : undefined
        }
        exchangeEnv={
          portfolio.status === "success" ? portfolio.data.exchange_env : undefined
        }
        backendConnected={backendConnected}
        backendLoading={backendLoading}
        schedulerRunning={schedulerRunning}
        killSwitchActive={
          portfolio.status === "success"
            ? portfolio.data.kill_switch_enabled
            : false
        }
        liveEnabled={false}
      />

      {actionMsg && (
        <div
          className={[
            "border px-3 py-2 text-[11px] font-mono",
            actionTone === "err"
              ? "border-terminal-danger/40 bg-terminal-danger/10 text-terminal-loss"
              : "border-terminal-accent/30 bg-terminal-accent/5 text-terminal-accent",
          ].join(" ")}
        >
          {actionMsg}
        </div>
      )}

      {portfolio.status === "loading" && <LoadingState label="Loading portfolio…" />}
      {portfolio.status === "error" && (
        <ErrorState message={portfolio.error} onRetry={portfolio.reload} />
      )}
      {portfolio.status === "success" && (
        <>
          <TradingModeIndicator
            mode={portfolio.data.trading_mode}
            runtimeMode={(portfolio.data as { runtime_mode?: string }).runtime_mode}
            exchangeEnv={portfolio.data.exchange_env}
          />
          <div className="flex flex-wrap gap-2">
            {portfolio.data.trading_paused && <Badge tone="warn">TRADING PAUSED</Badge>}
            {portfolio.data.kill_switch_enabled && <Badge tone="danger">KILL SWITCH</Badge>}
            <Badge tone="neutral">LIVE DISABLED</Badge>
          </div>
          <p className="text-[11px] font-mono text-terminal-dim">
            {(portfolio.data as { runtime_mode?: string }).runtime_mode || "PAPER"} MODE —
            fills are simulated. Results do not guarantee future performance.
          </p>

          <Card title="Portfolio" subtitle="Balance, equity, and total P&L">
            <PortfolioSummary data={portfolio.data} />
          </Card>

          <div className="grid min-w-0 gap-4 lg:grid-cols-2">
            <SchedulerControl
              running={schedulerRunning}
              onChanged={() => void system.reload()}
            />
            <KillSwitchControl
              active={portfolio.data.kill_switch_enabled}
              onChanged={(enabled) =>
                portfolio.setData({ ...portfolio.data, kill_switch_enabled: enabled })
              }
            />
          </div>

          {lastCycle && (
            <Card
              title="Latest execution activity"
              subtitle="Strategy → risk → paper fill (simulated)"
              actions={
                <Badge
                  tone={
                    String(lastCycle.signal_direction) === "buy"
                      ? "gain"
                      : String(lastCycle.signal_direction) === "sell"
                        ? "loss"
                        : "neutral"
                  }
                >
                  {String(lastCycle.signal_direction ?? "hold").toUpperCase()}
                </Badge>
              }
            >
              <dl className="grid gap-3 text-[11px] font-mono sm:grid-cols-2 lg:grid-cols-3">
                <div className="min-w-0">
                  <dt className="text-terminal-dim">Reason</dt>
                  <dd
                    className="mt-1 truncate text-terminal-text"
                    title={String(lastCycle.signal_reason ?? "—")}
                  >
                    {String(lastCycle.signal_reason ?? "—")}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-terminal-dim">Risk</dt>
                  <dd className="mt-1 text-terminal-text">
                    {String(lastCycle.risk_decision ?? "—")}
                    {lastCycle.risk_reason_code
                      ? ` · ${String(lastCycle.risk_reason_code)}`
                      : ""}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-terminal-dim">Order</dt>
                  <dd className="mt-1 truncate text-terminal-text">
                    {String(lastCycle.order_id ?? "none")}
                    {lastCycle.order_status ? ` [${String(lastCycle.order_status)}]` : ""}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-terminal-dim">Correlation</dt>
                  <dd className="mt-1 truncate text-terminal-text">
                    {String(lastCycle.correlation_id ?? "—")}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-terminal-dim">Accepted</dt>
                  <dd className="mt-1 text-terminal-text">
                    {String(Boolean(lastCycle.accepted))}
                    {lastCycle.idempotent_replay ? " · replay" : ""}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-terminal-dim">Candle</dt>
                  <dd className="mt-1 truncate text-terminal-text">
                    {formatTs(
                      typeof lastCycle.candle_open_time === "string"
                        ? lastCycle.candle_open_time
                        : null,
                    )}
                  </dd>
                </div>
                {indicators && (
                  <>
                    <div className="min-w-0">
                      <dt className="text-terminal-dim">Fast EMA</dt>
                      <dd className="mt-1 tabular-nums text-terminal-text">
                        {String(indicators.ema_fast ?? indicators.fast_ema ?? "—")}
                      </dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-terminal-dim">Slow EMA</dt>
                      <dd className="mt-1 tabular-nums text-terminal-text">
                        {String(indicators.ema_slow ?? indicators.slow_ema ?? "—")}
                      </dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-terminal-dim">Close</dt>
                      <dd className="mt-1 tabular-nums text-terminal-text">
                        {String(indicators.close ?? indicators.last_close ?? "—")}
                      </dd>
                    </div>
                  </>
                )}
              </dl>
            </Card>
          )}
        </>
      )}

      <Card
        title="System status"
        subtitle="Readiness · scheduler · reconciliation · last cycle (UTC)"
        actions={
          system.status === "success" ? (
            <Badge tone="accent">LIVE FEED</Badge>
          ) : system.status === "loading" ? (
            <Badge tone="neutral">LOADING</Badge>
          ) : (
            <Badge tone="danger">ERROR</Badge>
          )
        }
      >
        {system.status === "loading" && <LoadingState label="Loading system status…" />}
        {system.status === "error" && (
          <ErrorState message={system.error} onRetry={system.reload} />
        )}
        {system.status === "success" && <SystemStatusPanel data={system.data} />}
      </Card>

      <div className="grid min-w-0 gap-4 xl:grid-cols-2">
        <Card title="Equity curve" subtitle="Mark-to-market equity over recent sessions">
          {equity.status === "loading" && <LoadingState label="Loading equity curve…" />}
          {equity.status === "error" && (
            <ErrorState message={equity.error} onRetry={equity.reload} />
          )}
          {equity.status === "success" &&
            (equity.data.length ? (
              <EquityCurveChart data={equity.data} />
            ) : (
              <EmptyState title="No equity points" />
            ))}
        </Card>
        <Card title="Drawdown" subtitle="Peak-to-trough depth">
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
