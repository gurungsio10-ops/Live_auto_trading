"use client";

import { useState } from "react";
import { PortfolioSummary } from "@/components/PortfolioSummary";
import { TradingModeIndicator } from "@/components/TradingModeIndicator";
import { KillSwitchControl } from "@/components/KillSwitchControl";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import type {
  EquityPoint,
  PortfolioSummary as PortfolioSummaryType,
  SystemStatusPayload,
} from "@/lib/types";

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
      await Promise.all([portfolio.reload(), equity.reload()]);
    } catch (err) {
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
        setActionMsg(res.meta.backend_error);
        return;
      }
      const healthy = Boolean(res.data?.healthy);
      setActionMsg(
        healthy
          ? "Reconciliation OK"
          : `Reconciliation HALT: ${String(res.data?.detail ?? "mismatch")}`,
      );
      await system.reload();
    } catch (err) {
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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl tracking-[0.08em] uppercase text-terminal-text">
            Overview
          </h1>
          <p className="mt-1 text-xs text-terminal-dim">
            Portfolio, mode, kill switch, and equity trajectory.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={cyclePending}
            onClick={runPaperCycle}
          >
            {cyclePending ? "Running…" : "Run one paper cycle"}
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
                ? "Resume trading"
                : "Pause trading"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={exportPending}
            onClick={exportJournal}
          >
            {exportPending ? "Exporting…" : "Export journal"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={reconPending}
            onClick={runReconciliation}
          >
            {reconPending ? "Reconciling…" : "Run reconciliation"}
          </Button>
          <Button
            type="button"
            variant="danger"
            disabled={resetPending}
            onClick={resetPaperAccount}
          >
            {resetPending ? "Resetting…" : "Reset paper account"}
          </Button>
        </div>
      </div>

      <Card title="System status" subtitle="Backend connectivity, scheduler, reconciliation (UTC)">
        {system.status === "loading" && <LoadingState label="Loading system status…" />}
        {system.status === "error" && (
          <ErrorState message={system.error} onRetry={system.reload} />
        )}
        {system.status === "success" && (
          <dl className="grid gap-2 text-[11px] font-mono sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="text-terminal-dim">Ready</dt>
              <dd>{String(system.data.ready?.status ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Trading mode</dt>
              <dd>{String(system.data.health?.trading_mode ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Kill switch</dt>
              <dd>{String(system.data.health?.kill_switch_enabled ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Scheduler</dt>
              <dd>
                {JSON.stringify(
                  (system.data.health?.scheduler as Record<string, unknown>) ?? {},
                )}
              </dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Reconciliation</dt>
              <dd>
                {JSON.stringify(
                  (system.data.health?.reconciliation as Record<string, unknown>) ?? {},
                )}
              </dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Last cycle</dt>
              <dd>
                {JSON.stringify(
                  (system.data.metrics?.last_cycle as Record<string, unknown>) ?? {},
                )}
              </dd>
            </div>
          </dl>
        )}
      </Card>

      <DemoBanner
        demo={portfolio.meta?.demo || equity.meta?.demo}
        backendError={portfolio.meta?.backend_error || equity.meta?.backend_error}
      />
      {actionMsg && (
        <p className="text-[11px] font-mono text-terminal-accent">{actionMsg}</p>
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
          <p className="text-[11px] font-mono text-terminal-dim">
            {(portfolio.data as { runtime_mode?: string }).runtime_mode || "PAPER"} MODE —
            fills are simulated unless Spot Testnet is explicitly configured. Results do
            not guarantee future performance.
          </p>
          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <Card title="Portfolio summary" subtitle="Balance, equity, and P&L stack">
              <PortfolioSummary data={portfolio.data} />
            </Card>
            <KillSwitchControl
              active={portfolio.data.kill_switch_enabled}
              onChanged={(enabled) =>
                portfolio.setData({ ...portfolio.data, kill_switch_enabled: enabled })
              }
            />
          </div>
          {lastCycle && (
            <Card
              title="Latest paper cycle"
              subtitle="EMA crossover → risk → paper fill (simulated)"
            >
              <dl className="grid gap-2 text-[11px] font-mono sm:grid-cols-2">
                <div>
                  <dt className="text-terminal-dim">Signal</dt>
                  <dd>{String(lastCycle.signal_direction)}</dd>
                </div>
                <div>
                  <dt className="text-terminal-dim">Reason</dt>
                  <dd>{String(lastCycle.signal_reason ?? "—")}</dd>
                </div>
                <div>
                  <dt className="text-terminal-dim">Risk</dt>
                  <dd>
                    {String(lastCycle.risk_decision ?? "—")}{" "}
                    {lastCycle.risk_reason_code
                      ? `(${String(lastCycle.risk_reason_code)})`
                      : ""}
                  </dd>
                </div>
                <div>
                  <dt className="text-terminal-dim">Order</dt>
                  <dd>
                    {String(lastCycle.order_id ?? "none")}{" "}
                    {lastCycle.order_status ? `[${String(lastCycle.order_status)}]` : ""}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-terminal-dim">EMA indicators</dt>
                  <dd>{JSON.stringify(lastCycle.indicators ?? {})}</dd>
                </div>
              </dl>
            </Card>
          )}
        </>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
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
