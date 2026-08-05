"use client";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { TimestampValue } from "@/components/values";

export type SchedulerView = {
  status: "running" | "paused" | "disabled" | "error";
  intervalSeconds?: number | null;
  lastSuccessAt?: string | null;
  lastFailureAt?: string | null;
  nextRunAt?: string | null;
  activeStrategy?: string | null;
  symbol?: string | null;
  timeframe?: string | null;
  recentResult?: string | null;
  cyclesCompleted?: number | null;
  lastError?: string | null;
  details?: Record<string, unknown> | null;
};

function statusTone(status: SchedulerView["status"]) {
  switch (status) {
    case "running":
      return "gain" as const;
    case "paused":
      return "warn" as const;
    case "disabled":
      return "neutral" as const;
    case "error":
      return "danger" as const;
  }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] uppercase tracking-wide text-terminal-dim">{label}</dt>
      <dd className="mt-1 truncate text-xs font-mono text-terminal-text">{children}</dd>
    </div>
  );
}

export function SchedulerStatusCard({ data }: { data: SchedulerView }) {
  return (
    <Card
      title="Scheduler"
      subtitle="Paper cycle automation"
      actions={<Badge tone={statusTone(data.status)}>{data.status}</Badge>}
    >
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <Field label="Interval">
          {data.intervalSeconds != null ? `${data.intervalSeconds}s` : "—"}
        </Field>
        <Field label="Last success">
          {data.lastSuccessAt ? <TimestampValue value={data.lastSuccessAt} compact /> : "—"}
        </Field>
        <Field label="Last failure">
          {data.lastFailureAt ? <TimestampValue value={data.lastFailureAt} compact /> : "—"}
        </Field>
        <Field label="Next run">
          {data.nextRunAt ? <TimestampValue value={data.nextRunAt} compact /> : "—"}
        </Field>
        <Field label="Strategy">{data.activeStrategy ?? "—"}</Field>
        <Field label="Symbol / TF">
          {data.symbol && data.timeframe
            ? `${data.symbol} · ${data.timeframe}`
            : data.symbol ?? data.timeframe ?? "—"}
        </Field>
        <Field label="Recent result">{data.recentResult ?? "—"}</Field>
        <Field label="Cycles">{data.cyclesCompleted ?? "—"}</Field>
      </dl>
      {(data.lastError || data.details) && (
        <details className="mt-4 border border-terminal-border bg-terminal-bg/40 p-3">
          <summary className="cursor-pointer text-[11px] uppercase tracking-wide text-terminal-dim">
            Technical details
          </summary>
          <div className="mt-2 space-y-2 text-[11px] font-mono text-terminal-dim">
            {data.lastError ? <p>Error: {data.lastError}</p> : null}
            {data.details ? (
              <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all">
                {JSON.stringify(data.details, null, 2)}
              </pre>
            ) : null}
          </div>
        </details>
      )}
    </Card>
  );
}

export function schedulerFromStatus(raw: Record<string, unknown> | null | undefined): SchedulerView {
  const scheduler = (raw?.scheduler as Record<string, unknown> | undefined) ?? raw ?? {};
  const enabled = Boolean(scheduler.enabled_by_config ?? scheduler.enabled);
  const running = Boolean(scheduler.running);
  const paused = Boolean(scheduler.paused_by_failures ?? scheduler.paused);
  const lastError = (scheduler.last_error as string | null | undefined) ?? null;

  let status: SchedulerView["status"] = "disabled";
  if (lastError && !running) status = "error";
  else if (!enabled) status = "disabled";
  else if (paused) status = "paused";
  else if (running) status = "running";
  else status = "paused";

  return {
    status,
    intervalSeconds:
      (scheduler.interval_seconds as number | undefined) ??
      (raw?.paper_cycle_interval_seconds as number | undefined) ??
      null,
    lastSuccessAt: (scheduler.last_success_at as string | null | undefined) ?? null,
    lastFailureAt: (scheduler.last_failure_at as string | null | undefined) ?? null,
    nextRunAt: (scheduler.next_run_at as string | null | undefined) ?? null,
    activeStrategy:
      (scheduler.active_strategy as string | undefined) ??
      (raw?.active_strategy as string | undefined) ??
      null,
    symbol: (scheduler.symbol as string | undefined) ?? (raw?.symbol as string | undefined) ?? null,
    timeframe:
      (scheduler.timeframe as string | undefined) ??
      (raw?.timeframe as string | undefined) ??
      null,
    recentResult:
      (scheduler.recent_result as string | undefined) ??
      (raw?.last_cycle_result as string | undefined) ??
      null,
    cyclesCompleted: (scheduler.cycles_completed as number | undefined) ?? null,
    lastError,
    details: scheduler,
  };
}
