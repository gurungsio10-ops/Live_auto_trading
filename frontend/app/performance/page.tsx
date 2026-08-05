"use client";

import Link from "next/link";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { useAsyncData } from "@/lib/use-async-data";
import type { PerformanceMetrics, StrategyRanking } from "@/lib/analytics";
import type { EquityPoint } from "@/lib/types";

type PerfPayload = {
  metrics: PerformanceMetrics;
  equity_curve: {
    balance_history: EquityPoint[];
    drawdown_history: { time: string; drawdown: string }[];
    daily_return_history: { date: string; return_pct: string }[];
  };
  monthly_performance: {
    month: string;
    trade_count: number;
    net_pnl: string;
    win_rate: string;
  }[];
  strategies: StrategyRanking[];
  banner?: string;
};

function money(v: string | undefined) {
  const n = Number(v ?? 0);
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

export default function PerformancePage() {
  const perf = useAsyncData<PerfPayload>("/api/analytics/performance");
  const risk = useAsyncData<{
    exposure: string;
    risk_score: string;
    kill_switch_enabled: boolean;
    drawdown: string;
  }>("/api/analytics/risk");

  if (perf.status === "loading") return <LoadingState label="Loading performance…" />;
  if (perf.status === "error") return <ErrorState message={perf.error} />;

  const m = perf.data.metrics;
  const curve = perf.data.equity_curve;
  const balancePoints: EquityPoint[] = (curve?.balance_history || []).map((p) => ({
    time: p.time,
    equity: p.equity,
    drawdown: "0",
  }));
  const ddPoints = (curve?.drawdown_history || []).map((p) => ({
    time: p.time,
    equity: "0",
    drawdown: p.drawdown,
  }));

  // win_rate is 0–1 fraction from engine
  const winPct = `${(Number(m.win_rate || 0) * 100).toFixed(1)}%`;
  const roi = `${Number(m.roi_pct || 0).toFixed(2)}%`;

  return (
    <div className="min-w-0 space-y-4" data-testid="performance-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl tracking-[0.08em] uppercase">
            Performance
          </h1>
          <p className="mt-1 text-xs text-terminal-dim">
            Paper evaluation metrics — simulated fills only.
          </p>
        </div>
        <Badge tone="accent">PAPER</Badge>
      </div>

      {perf.status === "success" && perf.meta?.demo ? <DemoBanner /> : null}

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Balance" value={money(m.current_balance)} />
        <Metric label="ROI" value={roi} />
        <Metric label="Today" value={money(m.daily_pnl)} />
        <Metric label="Open" value={String(m.open_position_count)} />
      </section>

      <Card title="Equity curve">
        {balancePoints.length ? (
          <EquityCurveChart data={balancePoints} />
        ) : (
          <p className="text-xs text-terminal-dim">No equity history yet.</p>
        )}
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card title="Drawdown">
          {ddPoints.length ? (
            <DrawdownChart data={ddPoints} />
          ) : (
            <p className="text-xs text-terminal-dim">No drawdown history yet.</p>
          )}
          <p className="mt-2 font-mono text-xs text-terminal-dim">
            Max DD: {(Number(m.maximum_drawdown || 0) * 100).toFixed(2)}%
          </p>
        </Card>
        <Card title="Win / loss">
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-terminal-dim">Win rate</dt>
              <dd className="font-mono text-terminal-accent">{winPct}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Profit factor</dt>
              <dd className="font-mono">{Number(m.profit_factor || 0).toFixed(2)}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Avg win</dt>
              <dd className="font-mono">{money(m.average_win)}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Avg loss</dt>
              <dd className="font-mono">{money(m.average_loss)}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Trades</dt>
              <dd className="font-mono">{m.trade_count}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Fees</dt>
              <dd className="font-mono">{money(m.total_fees)}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <Card title="Monthly performance">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-xs font-mono">
            <thead className="text-terminal-dim">
              <tr>
                <th className="py-2 pr-3">Month</th>
                <th className="py-2 pr-3">Trades</th>
                <th className="py-2 pr-3">Net PnL</th>
                <th className="py-2">Win rate</th>
              </tr>
            </thead>
            <tbody>
              {(perf.data.monthly_performance || []).length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-3 text-terminal-dim">
                    No closed trades this period.
                  </td>
                </tr>
              ) : (
                perf.data.monthly_performance.map((row) => (
                  <tr key={row.month} className="border-t border-terminal-border/60">
                    <td className="py-2 pr-3">{row.month}</td>
                    <td className="py-2 pr-3">{row.trade_count}</td>
                    <td className="py-2 pr-3">{money(row.net_pnl)}</td>
                    <td className="py-2">
                      {(Number(row.win_rate) * 100).toFixed(1)}%
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Strategies">
        <ul className="divide-y divide-terminal-border/70">
          {(perf.data.strategies || []).length === 0 ? (
            <li className="py-3 text-xs text-terminal-dim">No strategy ranking yet.</li>
          ) : (
            perf.data.strategies.map((s) => (
              <li
                key={s.strategy_name}
                className="flex min-h-[44px] items-center justify-between gap-3 py-3 text-sm"
              >
                <span className="font-display uppercase tracking-[0.08em]">
                  #{s.rank} {s.strategy_name}
                </span>
                <span className="font-mono text-xs text-terminal-dim">
                  {money(s.net_pnl)} · {(Number(s.win_rate) * 100).toFixed(0)}% · alloc{" "}
                  {(Number(s.capital_allocation_proxy) * 100).toFixed(1)}%
                </span>
              </li>
            ))
          )}
        </ul>
        <Link
          href="/strategies"
          className="mt-3 inline-flex min-h-[44px] items-center text-xs uppercase tracking-[0.1em] text-terminal-accent"
        >
          Manage strategies →
        </Link>
      </Card>

      <Card title="Risk">
        {risk.status === "success" ? (
          <dl className="grid grid-cols-2 gap-3 text-sm lg:grid-cols-4">
            <div>
              <dt className="text-terminal-dim">Exposure</dt>
              <dd className="font-mono">{money(risk.data.exposure)}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Risk score</dt>
              <dd className="font-mono">{risk.data.risk_score}</dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Drawdown</dt>
              <dd className="font-mono">
                {(Number(risk.data.drawdown) * 100).toFixed(2)}%
              </dd>
            </div>
            <div>
              <dt className="text-terminal-dim">Kill switch</dt>
              <dd className="font-mono">
                {risk.data.kill_switch_enabled ? "ON" : "OFF"}
              </dd>
            </div>
          </dl>
        ) : (
          <p className="text-xs text-terminal-dim">Risk panel unavailable.</p>
        )}
      </Card>

      <div className="flex flex-wrap gap-3 text-xs">
        <Link
          href="/trades"
          className="inline-flex min-h-[44px] items-center uppercase tracking-[0.1em] text-terminal-accent"
        >
          Trade journal →
        </Link>
        <Link
          href="/reports"
          className="inline-flex min-h-[44px] items-center uppercase tracking-[0.1em] text-terminal-accent"
        >
          Reports / export →
        </Link>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-terminal-border/80 bg-terminal-panel/40 px-3 py-3">
      <div className="text-[10px] uppercase tracking-[0.14em] text-terminal-dim">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg text-terminal-text">{value}</div>
    </div>
  );
}
