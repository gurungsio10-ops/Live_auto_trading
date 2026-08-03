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
import type { EquityPoint, PortfolioSummary as PortfolioSummaryType } from "@/lib/types";

export default function OverviewPage() {
  const portfolio = useAsyncData<PortfolioSummaryType>("/api/portfolio");
  const equity = useAsyncData<EquityPoint[]>("/api/equity-curve");
  const [pausePending, setPausePending] = useState(false);
  const [exportPending, setExportPending] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

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
        </div>
      </div>

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
          <TradingModeIndicator mode={portfolio.data.trading_mode} />
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
