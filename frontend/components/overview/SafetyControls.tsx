"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { SectionCard } from "@/components/ui/SectionCard";
import { ConfirmDangerDialog } from "@/components/ui/ConfirmDangerDialog";
import { api } from "@/lib/api-client";
import type { PortfolioSummary } from "@/lib/types";

export function SafetyControls({
  portfolio,
  onPortfolioChange,
  onMessage,
  onCycleComplete,
}: {
  portfolio: PortfolioSummary;
  onPortfolioChange: (p: PortfolioSummary) => void;
  onMessage: (msg: string) => void;
  onCycleComplete: (data: Record<string, unknown>) => void;
}) {
  const [cyclePending, setCyclePending] = useState(false);
  const [pausePending, setPausePending] = useState(false);
  const [killPending, setKillPending] = useState(false);
  const [killOpen, setKillOpen] = useState(false);

  async function runCycle() {
    const ok = window.confirm(
      "Run one paper cycle?\n\nThis simulates a strategy → risk → paper fill path. No live money.",
    );
    if (!ok) return;
    setCyclePending(true);
    try {
      const res = await api.post<Record<string, unknown>>("/api/paper/cycle", {});
      if (res.meta?.backend_error) {
        onMessage(res.meta.backend_error);
        return;
      }
      onCycleComplete(res.data);
      onMessage(`Paper cycle: ${String(res.data?.signal_direction ?? "hold")} (simulated)`);
    } catch (err) {
      onMessage(err instanceof Error ? err.message : "Paper cycle failed");
    } finally {
      setCyclePending(false);
    }
  }

  async function togglePause() {
    const next = !portfolio.trading_paused;
    const ok = window.confirm(next ? "Pause new paper orders?" : "Resume paper trading?");
    if (!ok) return;
    setPausePending(true);
    try {
      const res = await api.post<PortfolioSummary>("/api/trading/pause", { paused: next });
      onPortfolioChange(res.data);
      onMessage(res.data.trading_paused ? "Trading paused" : "Trading resumed");
    } catch (err) {
      onMessage(err instanceof Error ? err.message : "Pause failed");
    } finally {
      setPausePending(false);
    }
  }

  async function toggleKill() {
    setKillPending(true);
    try {
      const res = await api.post<{ kill_switch_enabled: boolean }>("/api/kill-switch", {
        enabled: !portfolio.kill_switch_enabled,
      });
      onPortfolioChange({ ...portfolio, kill_switch_enabled: res.data.kill_switch_enabled });
      onMessage(
        res.data.kill_switch_enabled ? "Kill switch activated" : "Kill switch deactivated",
      );
      setKillOpen(false);
    } catch (err) {
      onMessage(err instanceof Error ? err.message : "Kill switch update failed");
    } finally {
      setKillPending(false);
    }
  }

  return (
    <SectionCard title="Safety controls" description="Protected paper-trading actions" className="h-full">
      <div className="flex flex-col gap-2">
        <Button type="button" variant="primary" size="lg" disabled={cyclePending} onClick={runCycle}>
          {cyclePending ? "Running…" : "Run one paper cycle"}
        </Button>
        <Button type="button" variant="warn" disabled={pausePending} onClick={togglePause}>
          {pausePending
            ? "…"
            : portfolio.trading_paused
              ? "Resume paper trading"
              : "Pause new paper orders"}
        </Button>
        <Button
          type="button"
          variant="dangerOutline"
          disabled={killPending}
          onClick={() => setKillOpen(true)}
        >
          {portfolio.kill_switch_enabled ? "Deactivate kill switch" : "Activate kill switch"}
        </Button>
      </div>

      <ConfirmDangerDialog
        open={killOpen}
        title={
          portfolio.kill_switch_enabled
            ? "Deactivate emergency stop?"
            : "Activate emergency stop?"
        }
        description={
          portfolio.kill_switch_enabled
            ? "New paper orders may be submitted again subject to risk checks."
            : "This will block new paper orders. Existing positions will remain unchanged unless the backend performs another action."
        }
        confirmLabel={portfolio.kill_switch_enabled ? "Deactivate" : "Activate kill switch"}
        pending={killPending}
        onClose={() => setKillOpen(false)}
        onConfirm={toggleKill}
      />
    </SectionCard>
  );
}
