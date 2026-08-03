"use client";

import { SignalFeed } from "@/components/SignalFeed";
import { Card } from "@/components/ui/Card";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { useAsyncData } from "@/lib/use-async-data";
import type { TradeSignal } from "@/lib/types";

export default function SignalsPage() {
  const { status, data, error, meta, reload } =
    useAsyncData<TradeSignal[]>("/api/signals");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase">Signals</h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Deterministic strategy signal feed with rationale and invalidation.
        </p>
      </div>
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />
      <Card title="Signal feed">
        {status === "loading" && <LoadingState label="Loading signals…" />}
        {status === "error" && <ErrorState message={error} onRetry={reload} />}
        {status === "success" && <SignalFeed signals={data} />}
      </Card>
    </div>
  );
}
