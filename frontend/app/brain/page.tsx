"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { useAsyncData } from "@/lib/use-async-data";

type BrainPayload = {
  title?: string;
  market_regime?: string;
  volatility_state?: string;
  trend_state?: string;
  momentum_state?: string;
  enabled_strategies?: Array<{ id?: string; name?: string; running?: boolean; selected?: boolean }>;
  strongest_observed_market?: string | null;
  weakest_observed_market?: string | null;
  current_risk_recommendation?: string;
  latest_decision_summary?: string;
  confidence?: string | null;
  confidence_source?: string;
  data_freshness?: string;
  ruleset_version?: string;
  explanation?: string;
  degraded_reasons?: string[];
  indicators_used?: Record<string, unknown>;
};

export default function BrainPage() {
  const brain = useAsyncData<BrainPayload | null>("/api/brain");

  return (
    <div className="space-y-4">
      <PageHeader
        title="Atlas Brain"
        description="Evidence-based market and risk summary from strategy outputs — not invented confidence."
        meta={<PaperTradingBadge />}
      />
      <PaperModeBanner />
      <DemoBanner demo={brain.meta?.demo} backendError={brain.meta?.backend_error} />

      {brain.status === "loading" && <LoadingState label="Loading Atlas Brain…" />}
      {brain.status === "error" && (
        <ErrorState title="Unable to load Atlas Brain" message={brain.error} onRetry={brain.reload} />
      )}
      {brain.status === "success" && !brain.data && (
        <EmptyState title="Atlas Brain unavailable" description={brain.meta?.backend_error} />
      )}
      {brain.status === "success" && brain.data && (
        <>
          <SectionCard title="Latest decision">
            <p className="text-[15px] leading-relaxed text-foreground">
              {brain.data.explanation || brain.data.latest_decision_summary}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone="primary">{brain.data.market_regime || "unknown"}</Badge>
              <Badge tone="neutral">Trend: {brain.data.trend_state || "unknown"}</Badge>
              <Badge tone="neutral">Vol: {brain.data.volatility_state || "unknown"}</Badge>
              <Badge tone="warning">{brain.data.current_risk_recommendation || "—"}</Badge>
            </div>
          </SectionCard>

          <div className="grid gap-3 md:grid-cols-2">
            <SectionCard title="Confidence">
              {brain.data.confidence ? (
                <p className="text-2xl font-semibold tabular text-foreground">{brain.data.confidence}</p>
              ) : (
                <p className="text-[14px] text-secondary">Unavailable — not invented</p>
              )}
              <p className="mt-1 text-[12px] text-muted">Source: {brain.data.confidence_source}</p>
            </SectionCard>
            <SectionCard title="Data freshness">
              <p className="text-[15px] font-semibold text-foreground">{brain.data.data_freshness}</p>
              <p className="mt-1 text-[12px] text-muted">Ruleset: {brain.data.ruleset_version}</p>
            </SectionCard>
            <SectionCard title="Strongest observed">
              <p className="text-[15px] text-foreground">
                {brain.data.strongest_observed_market || "—"}
              </p>
            </SectionCard>
            <SectionCard title="Weakest observed">
              <p className="text-[15px] text-foreground">
                {brain.data.weakest_observed_market || "—"}
              </p>
            </SectionCard>
          </div>

          <SectionCard title="Enabled strategies">
            {brain.data.enabled_strategies?.length ? (
              <ul className="space-y-2">
                {brain.data.enabled_strategies.map((s) => (
                  <li
                    key={String(s.id || s.name)}
                    className="flex items-center justify-between rounded-control border border-border px-3 py-2 text-[13px]"
                  >
                    <span className="text-foreground">{s.name}</span>
                    <Badge tone={s.running || s.selected ? "positive" : "neutral"}>
                      {s.running ? "Running" : s.selected ? "Selected" : "Idle"}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No strategies reported" />
            )}
          </SectionCard>

          {(brain.data.degraded_reasons || []).length ? (
            <SectionCard title="Degraded reasons">
              <ul className="list-disc space-y-1 pl-5 text-[13px] text-secondary">
                {brain.data.degraded_reasons!.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </SectionCard>
          ) : null}
        </>
      )}
    </div>
  );
}
