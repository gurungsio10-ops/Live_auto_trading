"use client";

import { StrategyCard } from "@/components/StrategyCard";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAsyncData } from "@/lib/use-async-data";
import type { Strategy, StrategyGovernanceStatus } from "@/lib/types";

const GOVERNANCE: StrategyGovernanceStatus[] = [
  "DRAFT",
  "BACKTESTING",
  "VALIDATED",
  "PAPER",
  "TESTNET",
  "LIVE_APPROVED",
  "RETIRED",
];

export default function StrategiesPage() {
  const { status, data, error, meta, reload, setData } =
    useAsyncData<Strategy[]>("/api/strategies");

  function upsert(updated: Strategy) {
    if (status !== "success") {
      reload();
      return;
    }
    setData(
      data.map((s) => {
        if (s.strategy_id === updated.strategy_id) return updated;
        if (updated.selected) return { ...s, selected: false };
        return s;
      }),
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase">Strategies</h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Governance ladder and paper runtime controls.
        </p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {GOVERNANCE.map((g) => (
          <Badge key={g} tone="neutral">
            {g}
          </Badge>
        ))}
      </div>
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />
      <Card title="Strategy registry">
        {status === "loading" && <LoadingState label="Loading strategies…" />}
        {status === "error" && <ErrorState message={error} onRetry={reload} />}
        {status === "success" &&
          (data.length === 0 ? (
            <EmptyState title="No strategies registered" />
          ) : (
            <div className="grid gap-3 lg:grid-cols-2">
              {data.map((s) => (
                <StrategyCard key={s.strategy_id} strategy={s} onUpdated={upsert} />
              ))}
            </div>
          ))}
      </Card>
    </div>
  );
}
