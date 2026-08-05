"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { useAsyncData } from "@/lib/use-async-data";
import { formatRelativeTime } from "@/lib/format";

type Decision = {
  id: string;
  timestamp?: string;
  strategy?: string | null;
  symbol?: string | null;
  action?: string;
  confidence?: string | null;
  rationale?: string | null;
  outcome?: string;
  rejection_reason?: string | null;
  order_id?: string | null;
  execution_result?: string | null;
  risk_checks?: { decision?: string | null; reason_code?: string | null };
};

type Feed = { items?: Decision[]; total?: number };

function outcomeTone(outcome?: string) {
  switch ((outcome || "").toUpperCase()) {
    case "EXECUTED":
      return "positive" as const;
    case "REJECTED":
    case "FAILED":
      return "negative" as const;
    case "SKIPPED":
      return "warning" as const;
    default:
      return "neutral" as const;
  }
}

export default function DecisionsPage() {
  const feed = useAsyncData<Feed>("/api/decisions", { limit: "50" });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Decision Feed"
        description="Backend-driven strategy decisions with risk outcomes. Rejected signals stay visible."
        meta={<PaperTradingBadge />}
      />
      <PaperModeBanner />
      <DemoBanner demo={feed.meta?.demo} backendError={feed.meta?.backend_error} />

      {feed.status === "loading" && <LoadingState label="Loading decisions…" />}
      {feed.status === "error" && (
        <ErrorState message={feed.error} onRetry={feed.reload} />
      )}
      {feed.status === "success" &&
        (!(feed.data.items || []).length ? (
          <EmptyState
            title="No decisions yet"
            description="Run one paper cycle or enable the scheduler to populate this feed."
          />
        ) : (
          <ul className="space-y-3">
            {(feed.data.items || []).map((d) => (
              <li key={d.id} className="rounded-card border border-border bg-surface-raised/40 p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[14px] font-semibold text-foreground">
                      {d.action} {d.symbol || ""}
                    </p>
                    <p className="mt-0.5 text-[12px] text-muted">
                      {d.strategy || "Strategy"} ·{" "}
                      {d.timestamp ? formatRelativeTime(d.timestamp) : "—"}
                    </p>
                  </div>
                  <Badge tone={outcomeTone(d.outcome)}>{d.outcome || "NO_ACTION"}</Badge>
                </div>
                {d.rationale ? (
                  <p className="mt-2 text-[13px] text-secondary">{d.rationale}</p>
                ) : null}
                <div className="mt-2 flex flex-wrap gap-2 text-[12px] text-muted">
                  {d.confidence ? <span>Confidence {d.confidence}</span> : null}
                  {d.risk_checks?.decision ? (
                    <span>
                      Risk {d.risk_checks.decision}
                      {d.risk_checks.reason_code ? ` (${d.risk_checks.reason_code})` : ""}
                    </span>
                  ) : null}
                  {d.rejection_reason ? <span>Reason: {d.rejection_reason}</span> : null}
                  {d.order_id ? <span>Order {d.order_id.slice(0, 10)}</span> : null}
                  {d.execution_result ? <span>{d.execution_result}</span> : null}
                </div>
              </li>
            ))}
          </ul>
        ))}
    </div>
  );
}
