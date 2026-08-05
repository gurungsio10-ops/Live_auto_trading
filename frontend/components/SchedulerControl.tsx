"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

/**
 * Explicit paper scheduler start / stop.
 * Confirm tokens match backend ConfirmBody contracts.
 * No live-money path.
 */
export function SchedulerControl({
  running,
  onChanged,
}: {
  running: boolean;
  onChanged?: () => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function start() {
    setPending(true);
    setError(null);
    setMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>("/api/trading/start", {
        confirm: "START_PAPER_TRADING",
      });
      if (res.meta?.backend_error) {
        setError(res.meta.backend_error);
        return;
      }
      setMsg("Scheduler started (paper)");
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Start failed");
    } finally {
      setPending(false);
    }
  }

  async function stop() {
    setPending(true);
    setError(null);
    setMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>("/api/trading/stop", {
        confirm: "STOP_PAPER_TRADING",
      });
      if (res.meta?.backend_error) {
        setError(res.meta.backend_error);
        return;
      }
      setMsg("Scheduler stopped");
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stop failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      data-testid="scheduler-control"
      className="border border-terminal-border bg-terminal-elevated/60 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-display text-xs uppercase tracking-[0.14em] text-terminal-text">
            Paper scheduler
          </p>
          <p className="mt-1 text-[11px] text-terminal-dim">
            Continuous paper cycles only. Live order routing remains impossible.
          </p>
        </div>
        <Badge tone={running ? "gain" : "neutral"}>
          {running ? "RUNNING" : "STOPPED"}
        </Badge>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="primary"
          disabled={pending || running}
          onClick={start}
          className="min-h-[44px] min-w-[44px]"
        >
          {pending && !running ? "Starting…" : "Start scheduler"}
        </Button>
        <Button
          type="button"
          variant="warn"
          disabled={pending || !running}
          onClick={stop}
          className="min-h-[44px] min-w-[44px]"
        >
          {pending && running ? "Stopping…" : "Stop scheduler"}
        </Button>
      </div>
      {msg && (
        <p className="mt-2 text-[11px] font-mono text-terminal-accent">{msg}</p>
      )}
      {error && (
        <p className="mt-2 text-[11px] font-mono text-terminal-loss">{error}</p>
      )}
    </div>
  );
}
