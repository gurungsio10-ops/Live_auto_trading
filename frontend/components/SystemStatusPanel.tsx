"use client";

import { Badge } from "@/components/ui/Badge";
import { formatBool, formatInt, formatTs } from "@/lib/format";
import type { SystemStatusPayload } from "@/lib/types";

type Tone = "neutral" | "accent" | "gain" | "loss" | "warn" | "danger";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function StatusTile({
  title,
  badge,
  badgeTone,
  rows,
}: {
  title: string;
  badge: string;
  badgeTone: Tone;
  rows: { label: string; value: string }[];
}) {
  return (
    <div className="min-w-0 overflow-hidden border border-terminal-border bg-terminal-elevated/40">
      <div className="flex items-center justify-between gap-2 border-b border-terminal-border/70 px-3 py-2">
        <p className="truncate font-display text-[10px] uppercase tracking-[0.14em] text-terminal-dim">
          {title}
        </p>
        <Badge tone={badgeTone}>{badge}</Badge>
      </div>
      <dl className="space-y-1.5 px-3 py-3 text-[11px] font-mono">
        {rows.map((row) => (
          <div key={row.label} className="flex min-w-0 items-baseline justify-between gap-3">
            <dt className="shrink-0 text-terminal-dim">{row.label}</dt>
            <dd
              title={row.value}
              className="min-w-0 truncate text-right tabular-nums text-terminal-text"
            >
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function SystemStatusPanel({ data }: { data: SystemStatusPayload }) {
  const health = asRecord(data.health);
  const ready = asRecord(data.ready);
  const metrics = asRecord(data.metrics);
  const scheduler = asRecord(health.scheduler ?? metrics.scheduler);
  const reconciliation = asRecord(health.reconciliation);
  const database = asRecord(health.database);
  const lastCycle = asRecord(metrics.last_cycle);

  const readyOk = String(ready.status ?? "") === "ready";
  const dbOk =
    database.ok === true ||
    ready.database_ok === true ||
    database.risk_flag === true;
  const recon = asRecord(reconciliation.last_result);
  const reconHealthy =
    reconciliation.healthy === true || recon.healthy === true;
  const reconHalted = reconciliation.halted === true || recon.halted === true;
  const schedEnabled = scheduler.enabled_by_config === true;
  const schedRunning = scheduler.running === true;
  const schedPaused = scheduler.paused_by_failures === true;

  let schedBadge = "DISABLED";
  let schedTone: Tone = "neutral";
  if (schedPaused) {
    schedBadge = "PAUSED";
    schedTone = "danger";
  } else if (schedRunning) {
    schedBadge = "RUNNING";
    schedTone = "gain";
  } else if (schedEnabled) {
    schedBadge = "IDLE";
    schedTone = "warn";
  }

  const cycleSignal = String(lastCycle.signal_direction ?? metrics.last_cycle_signal ?? "—");

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatusTile
        title="Readiness"
        badge={readyOk ? "READY" : "NOT READY"}
        badgeTone={readyOk ? "gain" : "danger"}
        rows={[
          { label: "Mode", value: String(health.trading_mode ?? ready.runtime_mode ?? "—") },
          { label: "Kill switch", value: formatBool(health.kill_switch_enabled) },
          {
            label: "Database",
            value: dbOk ? "OK" : String(ready.reason ?? database.detail ?? "UNHEALTHY"),
          },
          {
            label: "Live trading",
            value: formatBool(health.live_trading_enabled),
          },
        ]}
      />
      <StatusTile
        title="Scheduler"
        badge={schedBadge}
        badgeTone={schedTone}
        rows={[
          { label: "Config", value: schedEnabled ? "enabled" : "disabled" },
          { label: "Cycles", value: formatInt(Number(scheduler.cycles_completed ?? 0)) },
          {
            label: "Failures",
            value: formatInt(Number(scheduler.consecutive_failures ?? 0)),
          },
          {
            label: "Last OK",
            value: formatTs(
              typeof scheduler.last_success_at === "string"
                ? scheduler.last_success_at
                : null,
            ),
          },
          {
            label: "Last error",
            value:
              typeof scheduler.last_error === "string" && scheduler.last_error
                ? scheduler.last_error
                : "—",
          },
        ]}
      />
      <StatusTile
        title="Reconciliation"
        badge={reconHalted ? "HALTED" : reconHealthy ? "HEALTHY" : "DEGRADED"}
        badgeTone={reconHalted ? "danger" : reconHealthy ? "gain" : "warn"}
        rows={[
          {
            label: "Detail",
            value: String(recon.detail ?? reconciliation.detail ?? "—"),
          },
          {
            label: "Cash",
            value: String(recon.cash ?? "—"),
          },
          {
            label: "Positions",
            value: formatInt(Number(recon.position_count ?? 0)),
          },
          {
            label: "Checked",
            value: formatTs(
              typeof reconciliation.last_run_at === "string"
                ? reconciliation.last_run_at
                : typeof recon.checked_at === "string"
                  ? recon.checked_at
                  : null,
            ),
          },
        ]}
      />
      <StatusTile
        title="Last cycle"
        badge={cycleSignal === "—" ? "NONE" : cycleSignal.toUpperCase()}
        badgeTone={
          cycleSignal === "buy"
            ? "gain"
            : cycleSignal === "sell" || cycleSignal === "exit"
              ? "loss"
              : "neutral"
        }
        rows={[
          {
            label: "Risk",
            value: String(lastCycle.risk_decision ?? "—"),
          },
          {
            label: "Order",
            value: lastCycle.order_id
              ? `${String(lastCycle.order_id).slice(0, 10)}…`
              : "none",
          },
          {
            label: "Replay",
            value: formatBool(lastCycle.idempotent_replay),
          },
          {
            label: "Reject",
            value: String(lastCycle.reject_reason ?? "—"),
          },
        ]}
      />
    </div>
  );
}
