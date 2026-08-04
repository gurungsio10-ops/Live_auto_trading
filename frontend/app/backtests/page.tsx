"use client";

import { FormEvent, useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Button } from "@/components/ui/Button";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { MoneyValue, PercentageValue, PnlValue } from "@/components/values";
import { api } from "@/lib/api-client";
import { useAsyncData } from "@/lib/use-async-data";
import type { BacktestReport, Strategy } from "@/lib/types";

const STEPS = [
  "Select strategy",
  "Select symbol",
  "Select timeframe",
  "Select dataset",
  "Review assumptions",
  "Run backtest",
] as const;

export default function BacktestsPage() {
  const strategies = useAsyncData<Strategy[]>("/api/strategies");
  const history = useAsyncData<BacktestReport[]>("/api/backtests");
  const [strategyId, setStrategyId] = useState("");
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<BacktestReport | null>(null);
  const [demo, setDemo] = useState(false);
  const [backendError, setBackendError] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (strategies.status === "success" && strategies.data[0] && !strategyId) {
      setStrategyId(strategies.data[0].strategy_id);
      const firstSymbol = strategies.data[0].symbols[0];
      if (firstSymbol) setSymbol(firstSymbol);
      if (strategies.data[0].timeframe) setTimeframe(strategies.data[0].timeframe);
    }
  }, [strategies, strategyId]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (step < STEPS.length - 1) {
      setStep((s) => s + 1);
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const end = new Date();
      const start = new Date(end.getTime() - 30 * 24 * 3600_000);
      const res = await api.post<BacktestReport>("/api/backtests", {
        strategy_id: strategyId,
        symbol,
        timeframe,
        start: start.toISOString(),
        end: end.toISOString(),
      });
      setResult(res.data);
      setDemo(Boolean(res.meta?.demo));
      setBackendError(res.meta?.backend_error);
      await history.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run backtest");
    } finally {
      setRunning(false);
    }
  }

  if (strategies.status === "loading") {
    return <LoadingState label="Loading backtest setup…" />;
  }

  if (strategies.status === "error") {
    return (
      <ErrorState
        title="Unable to load strategies"
        message={strategies.error}
        onRetry={strategies.reload}
      />
    );
  }

  const metrics = result?.metrics;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Backtests"
        description="Evaluate strategy behaviour using historical or simulated data."
        meta={<PaperTradingBadge />}
      />

      <div
        className="rounded-card border border-warning/40 bg-warning-soft px-4 py-3 text-sm text-foreground"
        role="note"
      >
        Historical and simulated results do not guarantee future performance.
      </div>

      <DemoBanner
        demo={demo || strategies.meta?.demo || history.meta?.demo}
        backendError={backendError || strategies.meta?.backend_error}
      />
      {error ? (
        <ErrorState title="Unable to run backtest" message={error} onRetry={() => setError(null)} />
      ) : null}

      <SectionCard title={`Step ${step + 1}: ${STEPS[step]}`}>
        <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
          {step === 0 ? (
            <label className="block text-sm">
              <span className="mb-1.5 block text-secondary">Strategy</span>
              <select
                className="input-field"
                value={strategyId}
                onChange={(e) => setStrategyId(e.target.value)}
                required
              >
                {strategies.data.map((item) => (
                  <option key={item.strategy_id} value={item.strategy_id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {step === 1 ? (
            <label className="block text-sm">
              <span className="mb-1.5 block text-secondary">Symbol</span>
              <select
                className="input-field"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
              >
                {(
                  strategies.data.find((s) => s.strategy_id === strategyId)?.symbols ?? [
                    "BTC/USDT",
                    "ETH/USDT",
                  ]
                ).map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {step === 2 ? (
            <label className="block text-sm">
              <span className="mb-1.5 block text-secondary">Timeframe</span>
              <select
                className="input-field"
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
              >
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="4h">4h</option>
                <option value="1d">1d</option>
              </select>
            </label>
          ) : null}
          {step === 3 ? (
            <p className="text-sm text-secondary">
              Dataset: last 30 days relative to run time. Custom date-range controls are not exposed
              by a dedicated picker UI — the request sends an ISO window to the backend.
            </p>
          ) : null}
          {step === 4 ? (
            <ul className="list-disc space-y-1 pl-5 text-sm text-secondary">
              <li>Paper mode only — no live orders.</li>
              <li>Fees and slippage follow backend paper broker assumptions.</li>
              <li>Results are for research and must not be treated as forecasts.</li>
              <li>
                Strategy: {strategyId} · Symbol: {symbol} · Timeframe: {timeframe}
              </li>
            </ul>
          ) : null}
          {step === 5 ? (
            <p className="text-sm text-secondary">
              Ready to run a paper backtest for{" "}
              <strong className="text-foreground">{strategyId}</strong>.
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            {step > 0 ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => setStep((s) => s - 1)}
                disabled={running}
              >
                Back
              </Button>
            ) : null}
            <Button type="submit" variant="primary" disabled={running || !strategyId}>
              {running
                ? "Running…"
                : step < STEPS.length - 1
                  ? "Continue"
                  : "Run backtest"}
            </Button>
          </div>
        </form>
      </SectionCard>

      {result ? (
        <SectionCard title="Latest result" description={`Run ${result.run_id} · ${result.status}`}>
          {metrics ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <div>
                <p className="text-xs text-muted">Total return</p>
                <PercentageValue value={metrics.total_return} signed className="metric-value" />
              </div>
              <div>
                <p className="text-xs text-muted">Trades</p>
                <p className="metric-value text-foreground">{metrics.trade_count}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Win rate</p>
                <PercentageValue value={metrics.win_rate} className="metric-value" />
              </div>
              <div>
                <p className="text-xs text-muted">Max drawdown</p>
                <PercentageValue value={metrics.max_drawdown} className="metric-value" />
              </div>
              <div>
                <p className="text-xs text-muted">Fees</p>
                <MoneyValue value={metrics.fees_paid} className="metric-value" />
              </div>
              <div>
                <p className="text-xs text-muted">Profit factor</p>
                <p className="metric-value text-foreground">{metrics.profit_factor}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Net return</p>
                <PnlValue value={metrics.net_return} size="md" />
              </div>
            </div>
          ) : (
            <EmptyState
              title="Metrics unavailable"
              description={result.error ?? "The backtest finished without metric payload."}
            />
          )}
          {result.markdown_report ? (
            <details className="mt-4 rounded-card border border-border bg-surface-raised/40 p-3">
              <summary className="cursor-pointer text-sm font-medium text-foreground">
                Technical report
              </summary>
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap font-mono text-xs text-secondary">
                {result.markdown_report}
              </pre>
            </details>
          ) : null}
        </SectionCard>
      ) : null}

      <SectionCard title="Previous runs">
        {history.status === "loading" && <LoadingState label="Loading history…" />}
        {history.status === "error" && (
          <ErrorState message={history.error} onRetry={history.reload} />
        )}
        {history.status === "success" && !history.data.length && (
          <EmptyState title="No backtests yet" description="Run a paper backtest to see history." />
        )}
        {history.status === "success" && history.data.length > 0 && (
          <ul className="space-y-2">
            {history.data.map((run) => (
              <li
                key={run.run_id}
                className="rounded-card border border-border bg-surface-raised/40 px-3 py-2 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-foreground">
                    {run.strategy_id} · {run.status}
                  </span>
                  <span className="text-xs text-muted tabular">{run.created_at}</span>
                </div>
                {run.metrics ? (
                  <p className="mt-1 text-xs text-secondary">
                    Trades {run.metrics.trade_count} · Win rate{" "}
                    <PercentageValue value={run.metrics.win_rate} /> · Max DD{" "}
                    <PercentageValue value={run.metrics.max_drawdown} />
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}
