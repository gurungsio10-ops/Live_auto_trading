"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/Badge";
import { formatBool, formatInt, formatMoney, formatTs } from "@/lib/format";

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
    <div className="flex min-w-0 items-baseline justify-between gap-4 border-b border-terminal-border/60 py-1.5 text-xs">
      <span className="shrink-0 text-terminal-dim uppercase tracking-[0.08em]">{label}</span>
      <span
        title={value}
        className="min-w-0 truncate text-right font-mono tabular-nums text-terminal-text"
      >
        {value}
      </span>
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
  const scheduler = (r.scheduler ?? {}) as Record<string, unknown>;
  const lastCycle = r.last_cycle;
  const dbOk = String(r.database_status ?? "") === "ok";
  const schedEnabled = scheduler.enabled_by_config === true;
  const schedRunning = scheduler.running === true;

  return (
    <div className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-2xl tracking-[0.12em] text-terminal-accent">
            RECOVERY
          </h1>
          <p className="mt-1 text-xs text-terminal-dim">
            Backend source of truth — balances and PnL are never computed in the browser.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={dbOk ? "gain" : "danger"}>{dbOk ? "DB OK" : "DB UNHEALTHY"}</Badge>
          <Button onClick={() => void recovery.reload()} variant="ghost">
            Refresh
          </Button>
        </div>
      </div>

      {msg ? (
        <p className="border border-terminal-accent/30 bg-terminal-accent/5 px-3 py-2 text-xs font-mono text-terminal-accent">
          {msg}
        </p>
      ) : null}

      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <Card title="Runtime">
          <Row label="Runtime mode" value={String(r.runtime_mode ?? "—")} />
          <Row label="Trading mode" value={String(r.trading_mode ?? "—")} />
          <Row label="Trading enabled" value={formatBool(r.trading_enabled)} />
          <Row label="Trading paused" value={formatBool(r.trading_paused)} />
          <Row label="Kill switch" value={formatBool(r.kill_switch_enabled)} />
          <Row
            label="Last hydrated"
            value={formatTs(
              typeof r.last_hydrated_at === "string" ? r.last_hydrated_at : null,
            )}
          />
          <Row label="Persistence" value={String(r.persistence_status ?? "—")} />
          <Row label="Database" value={String(r.database_status ?? "—")} />
          <Row label="MD stale" value={formatBool(r.market_data_stale)} />
        </Card>

        <Card
          title="Scheduler"
          actions={
            <Badge
              tone={
                schedRunning ? "gain" : schedEnabled ? "warn" : "neutral"
              }
            >
              {schedRunning ? "RUNNING" : schedEnabled ? "IDLE" : "DISABLED"}
            </Badge>
          }
        >
          <Row label="Enabled" value={formatBool(scheduler.enabled_by_config)} />
          <Row label="Running" value={formatBool(scheduler.running)} />
          <Row
            label="Cycles"
            value={formatInt(Number(scheduler.cycles_completed ?? 0))}
          />
          <Row
            label="Failures"
            value={formatInt(Number(scheduler.consecutive_failures ?? 0))}
          />
          <Row
            label="Paused by failures"
            value={formatBool(scheduler.paused_by_failures)}
          />
          <Row
            label="Last success"
            value={formatTs(
              typeof scheduler.last_success_at === "string"
                ? scheduler.last_success_at
                : null,
            )}
          />
          <Row
            label="Last error"
            value={
              typeof scheduler.last_error === "string" && scheduler.last_error
                ? scheduler.last_error
                : "—"
            }
          />
        </Card>

        <Card title="Reconciliation">
          <Row label="Healthy" value={formatBool(recon.healthy)} />
          <Row label="Halted" value={formatBool(recon.halted)} />
          <Row
            label="Last run"
            value={formatTs(
              typeof recon.last_run_at === "string" ? recon.last_run_at : null,
            )}
          />
          <Row
            label="Last success"
            value={formatTs(
              typeof r.last_successful_reconciliation === "string"
                ? r.last_successful_reconciliation
                : null,
            )}
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
          <Row label="Recon healthy" value={formatBool(risk.reconciliation_healthy)} />
          <Row label="Risk engine" value={formatBool(risk.risk_engine_healthy)} />
          <Row label="Database" value={formatBool(risk.database_healthy)} />
          <Row label="Market data" value={formatBool(risk.market_data_healthy)} />
          <Row label="Circuit breaker" value={formatBool(risk.circuit_breaker_open)} />
          <Row
            label="CB reason"
            value={String(risk.circuit_breaker_reason || "—")}
          />
        </Card>

        <Card title="Portfolio snapshot">
          <Row label="Cash" value={formatMoney(String(portfolio.cash ?? "0"))} />
          <Row label="Equity" value={formatMoney(String(portfolio.equity ?? "0"))} />
          <Row
            label="Realised PnL"
            value={formatMoney(String(portfolio.realized_pnl ?? "0"))}
          />
          <Row
            label="Peak equity"
            value={formatMoney(String(portfolio.peak_equity ?? "0"))}
          />
          <Row
            label="Daily start equity"
            value={formatMoney(String(portfolio.daily_start_equity ?? "0"))}
          />
          <Row
            label="Open positions"
            value={formatInt(Number(portfolio.open_positions ?? 0))}
          />
          <Row
            label="Open orders"
            value={formatInt(Number(portfolio.open_orders ?? 0))}
          />
          <Row label="Fills" value={formatInt(Number(portfolio.fills ?? 0))} />
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
