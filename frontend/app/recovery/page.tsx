"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";

type RecoveryPayload = {
  recovery: {
    runtime_mode?: string;
    trading_mode?: string;
    kill_switch_enabled?: boolean;
    trading_enabled?: boolean;
    trading_paused?: boolean;
    last_hydrated_at?: string | null;
    persistence_status?: string;
    database_status?: string;
    market_data_stale?: boolean;
    scheduler?: Record<string, unknown>;
    last_cycle?: Record<string, unknown> | null;
    reconciliation?: Record<string, unknown>;
    risk?: Record<string, unknown>;
    portfolio?: Record<string, unknown>;
    strategy?: Record<string, unknown>;
    last_successful_reconciliation?: string | null;
    source_of_truth?: string;
  };
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-terminal-border/60 py-1.5 text-xs">
      <span className="text-terminal-dim uppercase tracking-[0.08em]">{label}</span>
      <span className="font-mono text-terminal-text text-right break-all">{value}</span>
    </div>
  );
}

export default function RecoveryPage() {
  const recovery = useAsyncData<RecoveryPayload>("/api/recovery/status");
  const [pending, setPending] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function clearHalt() {
    const ok = window.confirm(
      "Clear durable reconciliation halt? Only after corrective action.",
    );
    if (!ok) return;
    setPending(true);
    setMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>("/api/recovery/clear-halt", {
        confirm: "CLEAR_RECONCILIATION_HALT",
      });
      if (res.meta?.backend_error) {
        setMsg(res.meta.backend_error);
        return;
      }
      setMsg("Reconciliation halt cleared (admin)");
      await recovery.reload();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Clear halt failed");
    } finally {
      setPending(false);
    }
  }

  if (recovery.status === "loading") return <LoadingState label="Loading recovery…" />;
  if (recovery.status === "error") {
    return <ErrorState message={recovery.error} onRetry={() => void recovery.reload()} />;
  }

  const r = recovery.data.recovery;
  const recon = (r.reconciliation ?? {}) as Record<string, unknown>;
  const risk = (r.risk ?? {}) as Record<string, unknown>;
  const portfolio = (r.portfolio ?? {}) as Record<string, unknown>;
  const lastCycle = r.last_cycle;

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl tracking-[0.12em] text-terminal-accent">
            RECOVERY
          </h1>
          <p className="mt-1 text-xs text-terminal-dim">
            Backend source of truth — balances and PnL are never computed in the browser.
          </p>
        </div>
        <Button onClick={() => void recovery.reload()} variant="ghost">
          Refresh
        </Button>
      </div>

      {msg ? (
        <p className="text-xs font-mono text-terminal-accent">{msg}</p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Runtime">
          <Row label="Runtime mode" value={String(r.runtime_mode ?? "—")} />
          <Row label="Trading mode" value={String(r.trading_mode ?? "—")} />
          <Row label="Trading enabled" value={String(r.trading_enabled)} />
          <Row label="Trading paused" value={String(r.trading_paused)} />
          <Row label="Kill switch" value={String(r.kill_switch_enabled)} />
          <Row label="Last hydrated" value={String(r.last_hydrated_at ?? "never")} />
          <Row label="Persistence" value={String(r.persistence_status ?? "—")} />
          <Row label="Database" value={String(r.database_status ?? "—")} />
          <Row label="MD stale" value={String(r.market_data_stale)} />
          <Row
            label="Scheduler"
            value={JSON.stringify(r.scheduler ?? {}, null, 0)}
          />
        </Card>

        <Card title="Reconciliation">
          <Row label="Healthy" value={String(recon.healthy)} />
          <Row label="Halted" value={String(recon.halted)} />
          <Row label="Last run" value={String(recon.last_run_at ?? "—")} />
          <Row
            label="Last success"
            value={String(r.last_successful_reconciliation ?? "—")}
          />
          <div className="mt-3">
            <Button onClick={() => void clearHalt()} disabled={pending}>
              {pending ? "Clearing…" : "Clear halt (admin)"}
            </Button>
            <p className="mt-2 text-[10px] text-terminal-dim">
              Requires server-side ADMIN_API_TOKEN via BFF — never exposed to the browser.
            </p>
          </div>
        </Card>

        <Card title="Risk health">
          <Row label="Recon healthy" value={String(risk.reconciliation_healthy)} />
          <Row label="Risk engine" value={String(risk.risk_engine_healthy)} />
          <Row label="Database" value={String(risk.database_healthy)} />
          <Row label="Market data" value={String(risk.market_data_healthy)} />
          <Row label="Circuit breaker" value={String(risk.circuit_breaker_open)} />
          <Row
            label="CB reason"
            value={String(risk.circuit_breaker_reason || "—")}
          />
        </Card>

        <Card title="Portfolio snapshot">
          <Row label="Cash" value={String(portfolio.cash ?? "—")} />
          <Row label="Equity" value={String(portfolio.equity ?? "—")} />
          <Row label="Realised PnL" value={String(portfolio.realized_pnl ?? "—")} />
          <Row label="Peak equity" value={String(portfolio.peak_equity ?? "—")} />
          <Row
            label="Daily start equity"
            value={String(portfolio.daily_start_equity ?? "—")}
          />
          <Row label="Open positions" value={String(portfolio.open_positions ?? 0)} />
          <Row label="Open orders" value={String(portfolio.open_orders ?? 0)} />
          <Row label="Fills" value={String(portfolio.fills ?? 0)} />
        </Card>

        <Card title="Last cycle">
          {lastCycle ? (
            <>
              <Row label="Correlation" value={String(lastCycle.correlation_id)} />
              <Row label="Accepted" value={String(lastCycle.accepted)} />
              <Row label="Direction" value={String(lastCycle.signal_direction)} />
              <Row label="Order status" value={String(lastCycle.order_status ?? "—")} />
              <Row label="Reject" value={String(lastCycle.reject_reason ?? "—")} />
              <Row label="Idempotent" value={String(lastCycle.idempotent_replay)} />
              <Row label="Message" value={String(lastCycle.message ?? "—")} />
            </>
          ) : (
            <p className="text-xs text-terminal-dim">No cycle recorded in this process.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
