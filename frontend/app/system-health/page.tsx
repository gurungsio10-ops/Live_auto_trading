"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { useAsyncData } from "@/lib/use-async-data";

type SystemHealth = {
  status?: string;
  version?: string;
  environment?: string;
  trading_mode?: string;
  live_trading_enabled?: boolean;
  kill_switch_enabled?: boolean;
  exchange_env?: string;
  database?: { ok?: boolean; latency_ms?: number; error?: string };
  market_data?: { ok?: boolean; label?: string; provider?: string };
  scheduler?: {
    enabled?: boolean;
    paused?: boolean;
    status?: string;
    worker_running?: boolean;
    last_result?: string | null;
  };
  risk_engine_ok?: boolean;
  timestamp?: string;
};

function overallTone(status?: string) {
  if (status === "ok" || status === "healthy") return "positive" as const;
  if (status === "degraded") return "warning" as const;
  if (status === "halted" || status === "error") return "negative" as const;
  return "neutral" as const;
}

export default function SystemHealthPage() {
  const health = useAsyncData<SystemHealth | null>("/api/system-health");

  const data = health.status === "success" ? health.data : null;
  const loadError =
    health.status === "error"
      ? health.error
      : health.status === "success" && (health.data == null || health.meta?.backend_error)
        ? health.meta?.backend_error ?? "System health unavailable"
        : null;

  return (
    <div className="space-y-4">
      <PageHeader
        title="System health"
        description="API, database, scheduler, kill switch and market-data posture for the paper platform."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={health.meta?.demo} backendError={health.meta?.backend_error} />

      {health.status === "loading" && <LoadingState label="Loading system health…" />}
      {loadError && (
        <ErrorState
          title="Unable to load system health"
          message={loadError}
          onRetry={health.reload}
        />
      )}

      {health.status === "success" && data && !health.meta?.backend_error && (
        <>
          <SectionCard
            title="Overall"
            actions={<Badge tone={overallTone(data.status)}>{data.status ?? "unknown"}</Badge>}
          >
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-[14px]">
              <Row label="Version" value={data.version ?? "—"} />
              <Row label="Environment" value={data.environment ?? "—"} />
              <Row label="Trading mode" value={data.trading_mode ?? "paper"} />
              <Row
                label="Live trading"
                value={data.live_trading_enabled ? "Enabled (unexpected)" : "Disabled"}
              />
              <Row label="Exchange env" value={data.exchange_env ?? "—"} />
              <Row
                label="Timestamp"
                value={data.timestamp ? new Date(data.timestamp).toLocaleString() : "—"}
              />
            </dl>
          </SectionCard>

          <div className="grid gap-4 md:grid-cols-2">
            <SectionCard title="API">
              <Row
                label="Status"
                value={
                  <Badge tone="positive">Reachable</Badge>
                }
              />
              <Row label="Detail" value="FastAPI system health responded" />
            </SectionCard>

            <SectionCard title="Database">
              <Row
                label="Status"
                value={
                  <Badge tone={data.database?.ok ? "positive" : "negative"}>
                    {data.database?.ok ? "OK" : "Unhealthy"}
                  </Badge>
                }
              />
              <Row
                label="Latency"
                value={
                  data.database?.latency_ms != null ? `${data.database.latency_ms} ms` : "—"
                }
              />
              {data.database?.error ? (
                <p className="mt-2 text-[13px] text-negative">{data.database.error}</p>
              ) : null}
            </SectionCard>

            <SectionCard title="Scheduler">
              <Row
                label="Status"
                value={
                  <Badge
                    tone={
                      data.scheduler?.enabled && !data.scheduler?.paused
                        ? "positive"
                        : data.scheduler?.paused
                          ? "warning"
                          : "neutral"
                    }
                  >
                    {data.scheduler?.status ??
                      (data.scheduler?.enabled
                        ? data.scheduler?.paused
                          ? "paused"
                          : "enabled"
                        : "disabled")}
                  </Badge>
                }
              />
              <Row label="Worker" value={data.scheduler?.worker_running ? "Running" : "Stopped"} />
              <Row label="Last result" value={data.scheduler?.last_result ?? "—"} />
            </SectionCard>

            <SectionCard title="Kill switch">
              <Row
                label="Status"
                value={
                  <Badge tone={data.kill_switch_enabled ? "negative" : "positive"}>
                    {data.kill_switch_enabled ? "Active" : "Clear"}
                  </Badge>
                }
              />
              <Row
                label="Risk engine"
                value={data.risk_engine_ok === false ? "Unhealthy" : "OK"}
              />
            </SectionCard>
          </div>

          <SectionCard title="Market data">
            <Row
              label="Status"
              value={
                <Badge tone={data.market_data?.ok === false ? "warning" : "positive"}>
                  {data.market_data?.ok === false ? "Degraded" : "Available"}
                </Badge>
              }
            />
            <Row label="Provider" value={data.market_data?.provider ?? "—"} />
            <p className="mt-3 text-[14px] leading-relaxed text-secondary">
              {data.market_data?.label ??
                "Paper cycles use offline fixtures unless a public provider is configured."}
            </p>
          </SectionCard>
        </>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border/70 py-2.5 text-[14px] last:border-0">
      <span className="text-secondary">{label}</span>
      <span className="text-right text-foreground">{value}</span>
    </div>
  );
}
