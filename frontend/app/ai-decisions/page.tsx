"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { DecisionCard } from "@/components/cards/DecisionCard";
import { useAsyncData } from "@/lib/use-async-data";
import type { RiskEvent, TradeSignal } from "@/lib/types";

export default function AiDecisionsPage() {
  const signals = useAsyncData<TradeSignal[]>("/api/signals");
  const risk = useAsyncData<RiskEvent[]>("/api/risk-events");

  return (
    <div className="space-y-4">
      <PageHeader
        title="AI Decisions"
        description="Understand current strategy signals, advisory insights and risk-engine outcomes."
      />

      <div className="rounded-card border border-info/30 bg-info-soft px-4 py-3 text-[13px] leading-relaxed text-foreground">
        Automated execution is controlled by deterministic strategy and risk rules. AI output is
        advisory unless explicitly identified otherwise.
      </div>

      <DemoBanner demo={signals.meta?.demo} backendError={signals.meta?.backend_error} />

      {signals.status === "loading" && <LoadingState label="Loading decisions…" />}
      {signals.status === "error" && (
        <ErrorState title="Unable to load decisions" message={signals.error} onRetry={signals.reload} />
      )}
      {signals.status === "success" &&
        (signals.data.length ? (
          <div className="space-y-4">
            {signals.data.map((s) => {
              const match =
                risk.status === "success"
                  ? risk.data.find((r) => r.symbol === s.symbol)
                  : undefined;
              return (
                <DecisionCard
                  key={s.id}
                  signal={s}
                  riskDecision={match?.decision}
                  riskCode={match?.reason_code}
                  execution={match ? `Risk ${match.decision.toLowerCase()}` : "Not available"}
                />
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="No strategy decision"
            description="The selected strategy has not generated a decision yet."
          />
        ))}
    </div>
  );
}
