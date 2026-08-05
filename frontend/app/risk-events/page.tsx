"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { RiskEventLog } from "@/components/RiskEventLog";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { useAsyncData } from "@/lib/use-async-data";
import type { RiskEvent } from "@/lib/types";

export default function RiskEventsPage() {
  const events = useAsyncData<RiskEvent[]>("/api/risk-events");

  return (
    <div className="space-y-4">
      <PageHeader
        title="Risk Events"
        description="Audit trail of risk-engine decisions for paper orders."
        meta={<PaperTradingBadge />}
      />
      <PaperModeBanner />
      <DemoBanner demo={events.meta?.demo} backendError={events.meta?.backend_error} />

      {events.status === "loading" && <LoadingState label="Loading risk events…" />}
      {events.status === "error" && (
        <ErrorState title="Unable to load risk events" message={events.error} onRetry={events.reload} />
      )}
      {events.status === "success" &&
        (events.data.length ? (
          <RiskEventLog events={events.data} />
        ) : (
          <EmptyState title="No risk events" description="No recent risk rules have been triggered." />
        ))}
    </div>
  );
}
