"use client";

import { RiskEventLog } from "@/components/RiskEventLog";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { useAsyncData } from "@/lib/use-async-data";
import type { RiskEvent } from "@/lib/types";

export default function RiskEventsPage() {
  const { status, data, error, meta, reload } =
    useAsyncData<RiskEvent[]>("/api/risk-events");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase">Risk events</h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Every decision persisted with an equally visible reason code.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge tone="gain">APPROVED</Badge>
        <Badge tone="loss">REJECTED</Badge>
        <Badge tone="warn">REDUCED</Badge>
        <Badge tone="danger">HALTED</Badge>
      </div>
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />
      <Card title="Risk decision log" subtitle="Reason codes are first-class, not footnotes">
        {status === "loading" && <LoadingState label="Loading risk events…" />}
        {status === "error" && <ErrorState message={error} onRetry={reload} />}
        {status === "success" && <RiskEventLog events={data} />}
      </Card>
    </div>
  );
}
