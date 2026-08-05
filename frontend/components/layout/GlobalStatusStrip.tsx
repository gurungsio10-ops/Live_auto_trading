"use client";

import { Circle, PauseCircle, PlayCircle, ShieldAlert, StopCircle, Timer } from "lucide-react";
import type { EngineState, SystemState } from "@/lib/status";
import { STATUS_LABEL } from "@/lib/status";

function Chip({
  icon,
  label,
  value,
  tone,
  title,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: "positive" | "warning" | "negative" | "info" | "neutral";
  title?: string;
}) {
  const toneClass =
    tone === "positive"
      ? "text-positive"
      : tone === "warning"
        ? "text-warning"
        : tone === "negative"
          ? "text-negative"
          : tone === "info"
            ? "text-info"
            : "text-secondary";
  return (
    <div
      className="flex min-w-0 items-center gap-2 rounded-control border border-border bg-surface px-3 py-2"
      title={title}
    >
      <span className={toneClass} aria-hidden>
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
        <p className={`truncate text-[13px] font-semibold ${toneClass}`}>{value}</p>
      </div>
    </div>
  );
}

export function GlobalStatusStrip({
  engine,
  system,
  killSwitch,
  lastUpdate,
  schedulerLabel,
  degradedReasons,
}: {
  engine: EngineState;
  system: SystemState;
  killSwitch: boolean;
  lastUpdate?: string | null;
  schedulerLabel?: string | null;
  degradedReasons?: string[];
}) {
  const engineTone =
    engine === "running"
      ? "positive"
      : engine === "paused" || engine === "degraded"
        ? "warning"
        : engine === "error"
          ? "negative"
          : "neutral";
  const systemTone =
    system === "online" || system === "ok" || system === "running"
      ? "positive"
      : system === "degraded" || system === "paused"
        ? "warning"
        : "negative";
  const EngineIcon =
    engine === "running" ? PlayCircle : engine === "paused" ? PauseCircle : StopCircle;
  const reasons = (degradedReasons || []).filter(Boolean);
  const reasonText = reasons.length ? reasons.join(" · ") : undefined;

  return (
    <div className="mb-5 space-y-2">
      <div
        className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-6"
        role="status"
        aria-live="polite"
      >
        <Chip
          icon={<Circle className="h-3.5 w-3.5 fill-current" />}
          label="Mode"
          value="Paper"
          tone="warning"
        />
        <Chip
          icon={<EngineIcon className="h-4 w-4" />}
          label="Engine"
          value={STATUS_LABEL[engine] ?? engine}
          tone={engineTone}
          title={reasonText}
        />
        <Chip
          icon={<Circle className="h-3.5 w-3.5 fill-current" />}
          label="System"
          value={STATUS_LABEL[system] ?? system}
          tone={systemTone}
          title={reasonText}
        />
        <Chip
          icon={<ShieldAlert className="h-4 w-4" />}
          label="Kill switch"
          value={killSwitch ? "Active" : "Inactive"}
          tone={killSwitch ? "negative" : "positive"}
        />
        <Chip
          icon={<Timer className="h-4 w-4" />}
          label="Scheduler"
          value={schedulerLabel ?? "—"}
          tone="neutral"
        />
        <Chip
          icon={<Circle className="h-3.5 w-3.5" />}
          label="Last update"
          value={lastUpdate ?? "—"}
          tone="neutral"
        />
      </div>
      {reasons.length ? (
        <div
          className="rounded-control border border-warning/35 bg-warning-soft px-3 py-2 text-[12px] text-secondary"
          role="note"
        >
          <span className="font-semibold text-warning">Degraded: </span>
          {reasonText}
        </div>
      ) : null}
    </div>
  );
}
