"use client";

import { useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { StrategyCard } from "@/components/StrategyCard";
import { useAsyncData } from "@/lib/use-async-data";
import type { Strategy } from "@/lib/types";

export default function StrategiesPage() {
  const { status, data, error, meta, reload, setData } = useAsyncData<Strategy[]>("/api/strategies");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Strategies"
        description="Review active paper-trading strategies, parameters and recent performance."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />

      {status === "loading" && <LoadingState label="Loading strategies…" />}
      {status === "error" && (
        <ErrorState title="Unable to load strategies" message={error} onRetry={reload} />
      )}
      {status === "success" && !data.length && (
        <EmptyState
          title="No strategies"
          description="No paper strategies are registered in the backend."
        />
      )}
      {status === "success" && data.length > 0 && (
        <div className="space-y-4">
          {data.map((strategy) => (
            <div key={strategy.strategy_id} className="space-y-2">
              <StrategyCard
                strategy={strategy}
                onUpdated={(updated) => {
                  setData((prev) =>
                    (prev ?? []).map((s) =>
                      s.strategy_id === updated.strategy_id ? updated : s,
                    ),
                  );
                }}
              />
              <div className="flex flex-wrap items-center gap-2 px-1">
                <PaperTradingBadge />
                {strategy.running ? <Badge tone="positive">Running</Badge> : null}
                {strategy.selected ? <Badge tone="primary">Selected</Badge> : null}
                <Button
                  type="button"
                  variant={selectedId === strategy.strategy_id ? "primary" : "secondary"}
                  size="md"
                  onClick={() => setSelectedId(strategy.strategy_id)}
                >
                  Focus for review
                </Button>
              </div>
              <details className="rounded-card border border-border bg-surface-raised/40 p-3">
                <summary className="cursor-pointer text-sm font-medium text-foreground">
                  Assumptions & limitations
                </summary>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-secondary">
                  <li>Signals are deterministic rules, not guaranteed predictions.</li>
                  <li>Paper fills use configured fee and slippage assumptions.</li>
                  <li>Past evaluation results do not guarantee future performance.</li>
                  <li>
                    Market: {strategy.symbols.join(", ") || "Not available"} · Timeframe:{" "}
                    {strategy.timeframe || "Not available"}
                  </li>
                </ul>
              </details>
            </div>
          ))}
        </div>
      )}

      <SectionCard
        title="Strategy controls"
        description="Start, stop and parameter edits only when the backend supports paper controls."
      >
        <p className="text-sm text-secondary">
          Focused strategy:{" "}
          <span className="font-medium text-foreground">
            {selectedId
              ? data?.find((s) => s.strategy_id === selectedId)?.name ?? selectedId
              : "None selected"}
          </span>
        </p>
      </SectionCard>
    </div>
  );
}
