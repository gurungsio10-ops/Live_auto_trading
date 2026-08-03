"use client";

import { FormEvent, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import { formatPct, formatTs } from "@/lib/format";
import type { BacktestReport } from "@/lib/types";

export default function BacktestsPage() {
  const { status, data, error, meta, reload, setData } =
    useAsyncData<BacktestReport[]>("/api/backtests");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [view, setView] = useState<"markdown" | "json">("markdown");

  const [strategyId, setStrategyId] = useState("ema_trend");
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [start, setStart] = useState("2024-01-01");
  const [end, setEnd] = useState("2024-06-01");

  const selected =
    status === "success"
      ? data.find((b) => b.run_id === (selectedId ?? data[0]?.run_id)) ?? null
      : null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setFormError(null);
    try {
      const res = await api.post<BacktestReport>("/api/backtests", {
        strategy_id: strategyId,
        symbol,
        timeframe,
        start,
        end,
        initial_cash: "10000",
      });
      if (status === "success") setData([res.data, ...data]);
      else reload();
      setSelectedId(res.data.run_id);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setPending(false);
    }
  }

  const field =
    "w-full border border-terminal-border bg-terminal-bg px-2 py-1.5 text-xs text-terminal-text outline-none focus:border-terminal-accent font-mono";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase">Backtests</h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Submit runs and inspect JSON / Markdown reports.
        </p>
      </div>
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />

      <div className="grid gap-4 xl:grid-cols-[300px_1fr]">
        <Card title="Submit backtest">
          <form onSubmit={onSubmit} className="space-y-2">
            <label className="block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
              Strategy
              <input
                className={`${field} mt-1`}
                value={strategyId}
                onChange={(e) => setStrategyId(e.target.value)}
                required
              />
            </label>
            <label className="block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
              Symbol
              <input
                className={`${field} mt-1`}
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                required
              />
            </label>
            <label className="block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
              Timeframe
              <input
                className={`${field} mt-1`}
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                required
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
                Start
                <input
                  type="date"
                  className={`${field} mt-1`}
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  required
                />
              </label>
              <label className="block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
                End
                <input
                  type="date"
                  className={`${field} mt-1`}
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  required
                />
              </label>
            </div>
            <Button type="submit" variant="primary" className="w-full" disabled={pending}>
              {pending ? "Submitting…" : "Run backtest"}
            </Button>
            {formError && (
              <p className="text-[11px] text-terminal-loss font-mono">{formError}</p>
            )}
          </form>
        </Card>

        <div className="space-y-4">
          <Card title="Runs">
            {status === "loading" && <LoadingState label="Loading backtests…" />}
            {status === "error" && <ErrorState message={error} onRetry={reload} />}
            {status === "success" &&
              (data.length === 0 ? (
                <EmptyState title="No backtests yet" />
              ) : (
                <ul className="divide-y divide-terminal-border border border-terminal-border">
                  {data.map((b) => (
                    <li key={b.run_id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(b.run_id)}
                        className={[
                          "flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-xs hover:bg-terminal-muted/40",
                          selected?.run_id === b.run_id ? "bg-terminal-accent/10" : "",
                        ].join(" ")}
                      >
                        <span className="font-mono">
                          <span className="text-terminal-accent">{b.strategy_id}</span>{" "}
                          <span className="text-terminal-dim">{b.run_id}</span>
                        </span>
                        <span className="flex items-center gap-2">
                          <span className="text-terminal-dim">{formatTs(b.created_at)}</span>
                          <Badge
                            tone={
                              b.status === "completed"
                                ? "gain"
                                : b.status === "failed"
                                  ? "loss"
                                  : "warn"
                            }
                          >
                            {b.status}
                          </Badge>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ))}
          </Card>

          <Card
            title="Report"
            actions={
              <div className="flex gap-1">
                <Button
                  type="button"
                  variant={view === "markdown" ? "primary" : "ghost"}
                  onClick={() => setView("markdown")}
                >
                  Markdown
                </Button>
                <Button
                  type="button"
                  variant={view === "json" ? "primary" : "ghost"}
                  onClick={() => setView("json")}
                >
                  JSON
                </Button>
              </div>
            }
          >
            {!selected && <EmptyState title="Select a run" />}
            {selected && (
              <div className="space-y-3">
                {selected.metrics && (
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-4 text-xs font-mono">
                    <div className="border border-terminal-border p-2">
                      <p className="text-terminal-dim">Return</p>
                      <p>{formatPct(selected.metrics.total_return)}</p>
                    </div>
                    <div className="border border-terminal-border p-2">
                      <p className="text-terminal-dim">Max DD</p>
                      <p className="text-loss">{formatPct(selected.metrics.max_drawdown)}</p>
                    </div>
                    <div className="border border-terminal-border p-2">
                      <p className="text-terminal-dim">Sharpe</p>
                      <p>{selected.metrics.sharpe}</p>
                    </div>
                    <div className="border border-terminal-border p-2">
                      <p className="text-terminal-dim">Trades</p>
                      <p>{selected.metrics.trade_count}</p>
                    </div>
                  </div>
                )}
                <pre className="max-h-[420px] overflow-auto border border-terminal-border bg-terminal-bg p-3 text-[11px] leading-relaxed text-terminal-text whitespace-pre-wrap">
                  {view === "markdown"
                    ? selected.markdown_report || "No markdown report."
                    : JSON.stringify(selected.json_report ?? selected, null, 2)}
                </pre>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
