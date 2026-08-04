"use client";

import { Circle, PauseCircle, PlayCircle, ShieldAlert, StopCircle } from "lucide-react";
import type { EngineState, SystemState } from "@/lib/status";
import { STATUS_LABEL } from "@/lib/status";

function Chip({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: "positive" | "warning" | "negative" | "info" | "neutral";
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
    <div className="flex min-w-0 items-center gap-2 rounded-control border border-border bg-surface px-3 py-2">
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
}: {
  engine: EngineState;
  system: SystemState;
  killSwitch: boolean;
  lastUpdate?: string | null;
}) {
  const engineTone =
    engine === "running" ? "positive" : engine === "paused" ? "warning" : "neutral";
  const systemTone =
    system === "online" ? "positive" : system === "degraded" ? "warning" : "negative";
  const EngineIcon =
    engine === "running" ? PlayCircle : engine === "paused" ? PauseCircle : StopCircle;

  return (
    <div
      className="mb-5 grid grid-cols-2 gap-2 md:grid-cols-5"
      role="status"
      aria-live="polite"
    >
      <Chip icon={<Circle className="h-3.5 w-3.5 fill-current" />} label="Mode" value="Paper" tone="warning" />
      <Chip
        icon={<EngineIcon className="h-4 w-4" />}
        label="Engine"
        value={STATUS_LABEL[engine]}
        tone={engineTone}
      />
      <Chip
        icon={<Circle className="h-3.5 w-3.5 fill-current" />}
        label="System"
        value={STATUS_LABEL[system]}
        tone={systemTone}
      />
      <Chip
        icon={<ShieldAlert className="h-4 w-4" />}
        label="Kill switch"
        value={killSwitch ? "Active" : "Inactive"}
        tone={killSwitch ? "negative" : "positive"}
      />
      <Chip
        icon={<Circle className="h-3.5 w-3.5" />}
        label="Last update"
        value={lastUpdate ?? "—"}
        tone="neutral"
      />
    </div>
  );
}
