"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { TimestampValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";

type AuditEvent = {
  id: string;
  event_type?: string;
  severity?: string;
  message?: string;
  correlation_id?: string | null;
  order_id?: string | null;
  created_at?: string;
  payload?: Record<string, unknown>;
};

type AuditPage = {
  items: AuditEvent[];
  total?: number;
};

function severityTone(severity?: string) {
  const s = (severity ?? "").toLowerCase();
  if (s === "error" || s === "critical") return "negative" as const;
  if (s === "warning" || s === "warn") return "warning" as const;
  if (s === "info") return "info" as const;
  return "neutral" as const;
}

export default function AuditPage() {
  const events = useAsyncData<AuditPage>("/api/audit/events");

  const items =
    events.status === "success" && Array.isArray(events.data?.items) ? events.data.items : [];
  const backendError = events.meta?.backend_error;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Audit journal"
        description="Durable paper-trading journal events for signals, risk checks, orders and system actions."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={events.meta?.demo} backendError={backendError} />

      {events.status === "loading" && <LoadingState label="Loading audit journal…" />}
      {events.status === "error" && (
        <ErrorState
          title="Unable to load audit journal"
          message={events.error}
          onRetry={events.reload}
        />
      )}

      {events.status === "success" && backendError && items.length === 0 && (
        <ErrorState
          title="Unable to load audit journal"
          message={backendError}
          onRetry={events.reload}
        />
      )}

      {events.status === "success" && !backendError && (
        <SectionCard title="Journal events" description="Newest first">
          {items.length ? (
            <ol className="space-y-3">
              {items.map((e) => (
                <li key={e.id} className="rounded-control border border-border px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="neutral">{e.event_type ?? "event"}</Badge>
                      {e.severity ? (
                        <Badge tone={severityTone(e.severity)}>{e.severity}</Badge>
                      ) : null}
                    </div>
                    {e.created_at ? <TimestampValue value={e.created_at} /> : null}
                  </div>
                  <p className="mt-2 text-[14px] text-foreground">{e.message ?? "—"}</p>
                  <p className="mt-1 text-[12px] text-muted">
                    {e.correlation_id ? `Correlation · ${e.correlation_id}` : "No correlation id"}
                    {e.order_id ? ` · Order · ${e.order_id}` : ""}
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState
              title="No audit events"
              description="Paper cycle and risk activity will appear in the durable journal."
            />
          )}
        </SectionCard>
      )}
    </div>
  );
}
