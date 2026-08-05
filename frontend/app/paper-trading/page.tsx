"use client";

import { useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { Button } from "@/components/ui/Button";
import { MoneyValue, PercentageValue, PnlValue, TimestampValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";

type PaperCycle = {
  id: string;
  correlation_id?: string | null;
  symbol?: string;
  timeframe?: string;
  strategy_id?: string;
  status?: string;
  signal_direction?: string | null;
  order_id?: string | null;
  risk_decision?: string | null;
  risk_reason_code?: string | null;
  duration_ms?: number | null;
  error_summary?: string | null;
  created_at?: string;
};

type CyclesPage = {
  items: PaperCycle[];
  total?: number;
};

type PaperAnalytics = {
  starting_balance?: string;
  current_equity?: string;
  total_return?: string | null;
  realized_pnl?: string;
  unrealized_pnl?: string;
  fees_paid?: string;
  maximum_drawdown?: string;
  win_rate?: string | null;
  profit_factor?: string | null;
  average_win?: string | null;
  average_loss?: string | null;
  expectancy?: string | null;
  total_trades?: number;
  winning_trades?: number;
  losing_trades?: number;
  insufficient_data?: boolean;
  notes?: string[];
};

export default function PaperTradingPage() {
  const cycles = useAsyncData<CyclesPage>("/api/paper-cycles");
  const analytics = useAsyncData<PaperAnalytics | null>("/api/analytics/paper");
  const [cyclePending, setCyclePending] = useState(false);
  const [cycleMsg, setCycleMsg] = useState<string | null>(null);
  const [lastCycle, setLastCycle] = useState<Record<string, unknown> | null>(null);

  async function runOneCycle() {
    const ok = window.confirm(
      "Run one paper cycle?\n\nThis simulates a strategy → risk → paper fill path. No live money.",
    );
    if (!ok) return;
    setCyclePending(true);
    setCycleMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>("/api/paper/cycle", {});
      if (res.meta?.backend_error || res.data == null) {
        setCycleMsg(res.meta?.backend_error ?? "Paper cycle failed");
        return;
      }
      setLastCycle(res.data);
      setCycleMsg(`Paper cycle: ${String(res.data?.signal_direction ?? "hold")} (simulated)`);
      cycles.reload();
      analytics.reload();
    } catch (err) {
      setCycleMsg(err instanceof Error ? err.message : "Paper cycle failed");
    } finally {
      setCyclePending(false);
    }
  }

  const cycleItems =
    cycles.status === "success" && Array.isArray(cycles.data?.items) ? cycles.data.items : [];
  const analyticsData =
    analytics.status === "success" && analytics.data && !analytics.meta?.backend_error
      ? analytics.data
      : null;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Paper trading"
        description="Run paper cycles, review cycle history and descriptive analytics. Simulated only."
        meta={<PaperTradingBadge />}
        actions={
          <Button type="button" variant="primary" disabled={cyclePending} onClick={runOneCycle}>
            {cyclePending ? "Running…" : "Run one paper cycle"}
          </Button>
        }
      />
      <DemoBanner
        demo={cycles.meta?.demo || analytics.meta?.demo}
        backendError={cycles.meta?.backend_error || analytics.meta?.backend_error}
      />

      {cycleMsg ? (
        <p className="text-[13px] text-secondary" role="status">
          {cycleMsg}
        </p>
      ) : null}

      {lastCycle ? (
        <SectionCard title="Last cycle result" description="Most recent on-demand paper cycle">
          <pre className="max-h-48 overflow-auto rounded-control border border-border bg-surface-raised/50 p-3 text-[12px] font-mono text-secondary">
            {JSON.stringify(lastCycle, null, 2)}
          </pre>
        </SectionCard>
      ) : null}

      <SectionCard title="Analytics summary" description="Paper metrics from persisted state">
        {analytics.status === "loading" && <LoadingState label="Loading analytics…" />}
        {analytics.status === "error" && (
          <ErrorState message={analytics.error} onRetry={analytics.reload} />
        )}
        {analytics.status === "success" && analytics.meta?.backend_error && !analyticsData && (
          <ErrorState
            title="Analytics unavailable"
            message={analytics.meta.backend_error}
            onRetry={analytics.reload}
          />
        )}
        {analyticsData && (
          <>
            {analyticsData.insufficient_data ? (
              <Badge tone="warning" className="mb-3">
                Insufficient data
              </Badge>
            ) : null}
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-[14px]">
              <Metric
                label="Equity"
                value={
                  analyticsData.current_equity != null ? (
                    <MoneyValue value={analyticsData.current_equity} size="sm" />
                  ) : (
                    "—"
                  )
                }
              />
              <Metric
                label="Total return"
                value={
                  analyticsData.total_return != null ? (
                    <PercentageValue value={analyticsData.total_return} />
                  ) : (
                    "—"
                  )
                }
              />
              <Metric
                label="Realized PnL"
                value={
                  analyticsData.realized_pnl != null ? (
                    <PnlValue value={analyticsData.realized_pnl} size="sm" />
                  ) : (
                    "—"
                  )
                }
              />
              <Metric
                label="Max drawdown"
                value={
                  analyticsData.maximum_drawdown != null ? (
                    <PercentageValue value={analyticsData.maximum_drawdown} />
                  ) : (
                    "—"
                  )
                }
              />
              <Metric label="Trades" value={analyticsData.total_trades ?? "—"} />
              <Metric
                label="Win rate"
                value={
                  analyticsData.win_rate != null ? (
                    <PercentageValue value={analyticsData.win_rate} />
                  ) : (
                    "—"
                  )
                }
              />
              <Metric label="Profit factor" value={analyticsData.profit_factor ?? "—"} />
              <Metric label="Fees paid" value={analyticsData.fees_paid ?? "—"} />
            </dl>
            {analyticsData.notes?.length ? (
              <ul className="mt-4 space-y-1 text-[13px] text-secondary">
                {analyticsData.notes.map((n) => (
                  <li key={n}>· {n}</li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </SectionCard>

      <SectionCard title="Cycle history" description="Persisted paper cycle runs">
        {cycles.status === "loading" && <LoadingState label="Loading cycles…" />}
        {cycles.status === "error" && (
          <ErrorState message={cycles.error} onRetry={cycles.reload} />
        )}
        {cycles.status === "success" && cycles.meta?.backend_error && cycleItems.length === 0 && (
          <ErrorState
            title="Cycle history unavailable"
            message={cycles.meta.backend_error}
            onRetry={cycles.reload}
          />
        )}
        {cycles.status === "success" &&
          !cycles.meta?.backend_error &&
          (cycleItems.length ? (
            <ol className="space-y-3">
              {cycleItems.map((c) => (
                <li key={c.id} className="rounded-control border border-border px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="neutral">{c.status ?? "unknown"}</Badge>
                      {c.signal_direction ? (
                        <Badge tone="primary">{c.signal_direction}</Badge>
                      ) : null}
                    </div>
                    {c.created_at ? <TimestampValue value={c.created_at} /> : null}
                  </div>
                  <p className="mt-2 text-[14px] text-foreground">
                    {c.symbol ?? "—"} · {c.timeframe ?? "—"} · {c.strategy_id ?? "—"}
                  </p>
                  <p className="mt-1 text-[12px] text-muted">
                    Risk · {c.risk_decision ?? "—"}
                    {c.risk_reason_code ? ` · ${c.risk_reason_code}` : ""}
                    {c.duration_ms != null ? ` · ${c.duration_ms}ms` : ""}
                  </p>
                  {c.error_summary ? (
                    <p className="mt-1 text-[12px] text-negative">{c.error_summary}</p>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState
              title="No paper cycles yet"
              description="Run one paper cycle to populate history."
            />
          ))}
      </SectionCard>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[12px] text-muted">{label}</dt>
      <dd className="mt-1 text-foreground">{value}</dd>
    </div>
  );
}
