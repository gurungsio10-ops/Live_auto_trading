"use client";

import { Circle } from "lucide-react";
import { SectionCard } from "@/components/ui/SectionCard";
import type { EngineState, SystemState } from "@/lib/status";
import { STATUS_LABEL } from "@/lib/status";

export function EngineStatusCard({
  engine,
  system,
  strategyName,
  lastCycle,
}: {
  engine: EngineState;
  system: SystemState;
  strategyName?: string | null;
  lastCycle?: string | null;
}) {
  const tone =
    engine === "running" ? "text-positive" : engine === "paused" ? "text-warning" : "text-muted";

  return (
    <SectionCard title="Trading engine" description="Paper execution status" className="h-full">
      <dl className="space-y-3 text-[14px]">
        <div className="flex items-center justify-between gap-3">
          <dt className="text-secondary">Status</dt>
          <dd className={`inline-flex items-center gap-2 font-semibold ${tone}`}>
            <Circle className="h-2.5 w-2.5 fill-current" aria-hidden />
            {STATUS_LABEL[engine]}
          </dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt className="text-secondary">Strategy</dt>
          <dd className="truncate font-medium text-foreground">{strategyName ?? "Not available"}</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt className="text-secondary">Last cycle</dt>
          <dd className="text-foreground">{lastCycle ?? "Not available"}</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt className="text-secondary">System</dt>
          <dd className="font-medium text-foreground">{STATUS_LABEL[system]}</dd>
        </div>
      </dl>
    </SectionCard>
  );
}
