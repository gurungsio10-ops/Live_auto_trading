"use client";

import { useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { ConfirmDangerDialog } from "@/components/ui/ConfirmDangerDialog";
import { Button } from "@/components/ui/Button";
import { TimestampValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";

type SchedulerStatus = {
  name?: string;
  enabled?: boolean;
  paused?: boolean;
  status?: string;
  interval_seconds?: number;
  symbol?: string;
  timeframe?: string;
  strategy_id?: string;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_duration_ms?: number | null;
  last_result?: string | null;
  last_error?: string | null;
  last_correlation_id?: string | null;
  run_count?: number;
  fail_count?: number;
  worker_running?: boolean;
  trading_mode?: string;
  live_trading_enabled?: boolean;
};

function statusTone(status?: string, enabled?: boolean, paused?: boolean) {
  if (status === "error" || status === "failed") return "negative" as const;
  if (!enabled || status === "stopped" || status === "disabled") return "neutral" as const;
  if (paused || status === "paused") return "warning" as const;
  if (status === "running" || enabled) return "positive" as const;
  return "neutral" as const;
}

export default function SchedulerPage() {
  const status = useAsyncData<SchedulerStatus | null>("/api/scheduler/status");
  const [pending, setPending] = useState<"enable" | "disable" | "pause" | null>(null);
  const [enableOpen, setEnableOpen] = useState(false);
  const [disableOpen, setDisableOpen] = useState(false);
  const [pauseOpen, setPauseOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  async function runAction(
    kind: "enable" | "disable" | "pause",
    path: string,
    body?: Record<string, unknown>,
  ) {
    setPending(kind);
    setActionError(null);
    setActionMsg(null);
    try {
      const res = await api.post<SchedulerStatus | null>(path, body ?? {});
      if (res.meta?.backend_error || res.data == null) {
        setActionError(res.meta?.backend_error ?? "Scheduler action failed");
        return;
      }
      status.setData(res.data);
      setActionMsg(
        kind === "enable"
          ? "Paper scheduler enabled"
          : kind === "disable"
            ? "Paper scheduler disabled"
            : "Paper scheduler paused",
      );
      setEnableOpen(false);
      setDisableOpen(false);
      setPauseOpen(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Scheduler action failed");
    } finally {
      setPending(null);
    }
  }

  const data = status.status === "success" ? status.data : null;
  const loadError =
    status.status === "error"
      ? status.error
      : status.status === "success" && (status.data == null || status.meta?.backend_error)
        ? status.meta?.backend_error ?? "Scheduler status unavailable"
        : null;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Scheduler"
        description="Control the paper-cycle scheduler. This never starts live trading."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={status.meta?.demo} backendError={status.meta?.backend_error} />

      <SectionCard title="Paper only" description="Safety reminder">
        <p className="text-[14px] leading-relaxed text-secondary">
          The scheduler runs simulated paper cycles only. Enabling it does not place live orders,
          connect an exchange wallet, or imply live trading readiness.
        </p>
      </SectionCard>

      {status.status === "loading" && <LoadingState label="Loading scheduler status…" />}
      {loadError && (
        <ErrorState
          title="Unable to load scheduler status"
          message={loadError}
          onRetry={status.reload}
        />
      )}

      {status.status === "success" && data && !status.meta?.backend_error && (
        <SectionCard
          title="Scheduler status"
          description="Durable paper-cycle automation"
          actions={
            <Badge tone={statusTone(data.status, data.enabled, data.paused)}>
              {data.status ?? (data.enabled ? (data.paused ? "paused" : "enabled") : "disabled")}
            </Badge>
          }
        >
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-[14px]">
            <Field label="Enabled">{data.enabled ? "Yes" : "No"}</Field>
            <Field label="Paused">{data.paused ? "Yes" : "No"}</Field>
            <Field label="Worker">{data.worker_running ? "Running" : "Stopped"}</Field>
            <Field label="Interval">
              {data.interval_seconds != null ? `${data.interval_seconds}s` : "—"}
            </Field>
            <Field label="Strategy">{data.strategy_id ?? "—"}</Field>
            <Field label="Symbol / TF">
              {data.symbol && data.timeframe
                ? `${data.symbol} · ${data.timeframe}`
                : data.symbol ?? data.timeframe ?? "—"}
            </Field>
            <Field label="Last run">
              {data.last_run_at ? <TimestampValue value={data.last_run_at} /> : "—"}
            </Field>
            <Field label="Next run">
              {data.next_run_at ? <TimestampValue value={data.next_run_at} /> : "—"}
            </Field>
            <Field label="Last result">{data.last_result ?? "—"}</Field>
            <Field label="Runs">{data.run_count ?? "—"}</Field>
            <Field label="Failures">{data.fail_count ?? "—"}</Field>
            <Field label="Trading mode">{data.trading_mode ?? "paper"}</Field>
          </dl>
          {data.last_error ? (
            <p className="mt-4 text-[13px] text-negative" role="alert">
              Last error: {data.last_error}
            </p>
          ) : null}

          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            <Button
              type="button"
              variant="primary"
              disabled={pending !== null || data.enabled === true}
              onClick={() => setEnableOpen(true)}
            >
              Enable
            </Button>
            <Button
              type="button"
              variant="warn"
              disabled={pending !== null || data.paused === true}
              onClick={() => setPauseOpen(true)}
            >
              Pause
            </Button>
            <Button
              type="button"
              variant="dangerOutline"
              disabled={pending !== null || data.enabled === false}
              onClick={() => setDisableOpen(true)}
            >
              Disable
            </Button>
          </div>
        </SectionCard>
      )}

      {actionMsg ? (
        <p className="text-[13px] text-secondary" role="status">
          {actionMsg}
        </p>
      ) : null}
      {actionError ? (
        <ErrorState title="Scheduler action failed" message={actionError} />
      ) : null}

      <ConfirmDangerDialog
        open={enableOpen}
        title="Enable paper scheduler?"
        description="This starts automated paper cycles only. No live orders will be placed. Type ENABLE_PAPER_SCHEDULER to confirm."
        confirmLabel="Enable paper scheduler"
        requireText="ENABLE_PAPER_SCHEDULER"
        pending={pending === "enable"}
        onClose={() => setEnableOpen(false)}
        onConfirm={() =>
          runAction("enable", "/api/scheduler/enable", { confirm: "ENABLE_PAPER_SCHEDULER" })
        }
      />
      <ConfirmDangerDialog
        open={pauseOpen}
        title="Pause paper scheduler?"
        description="Paused scheduler will stop new paper cycles until resumed or re-enabled. Live trading is never involved."
        confirmLabel="Pause scheduler"
        pending={pending === "pause"}
        onClose={() => setPauseOpen(false)}
        onConfirm={() => runAction("pause", "/api/scheduler/pause", { paused: true })}
      />
      <ConfirmDangerDialog
        open={disableOpen}
        title="Disable paper scheduler?"
        description="The paper scheduler will stop. Existing paper positions are unchanged."
        confirmLabel="Disable scheduler"
        pending={pending === "disable"}
        onClose={() => setDisableOpen(false)}
        onConfirm={() => runAction("disable", "/api/scheduler/disable")}
      />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[12px] text-muted">{label}</dt>
      <dd className="mt-1 text-foreground">{children}</dd>
    </div>
  );
}
