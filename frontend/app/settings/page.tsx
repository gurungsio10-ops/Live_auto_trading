"use client";

import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { TradingModeIndicator } from "@/components/TradingModeIndicator";
import { useAsyncData } from "@/lib/use-async-data";
import { formatPct } from "@/lib/format";
import type { SettingsView } from "@/lib/types";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-terminal-border/70 py-2 text-xs">
      <span className="font-display uppercase tracking-[0.1em] text-terminal-dim">
        {label}
      </span>
      <span className="font-mono tabular-nums text-terminal-text">{value}</span>
    </div>
  );
}

export default function SettingsPage() {
  const { status, data, error, meta, reload } =
    useAsyncData<SettingsView>("/api/settings");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase">Settings</h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Read-only risk limits and trading mode. No live promotion controls.
        </p>
      </div>
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />

      {status === "loading" && <LoadingState label="Loading settings…" />}
      {status === "error" && <ErrorState message={error} onRetry={reload} />}
      {status === "success" && (
        <>
          <TradingModeIndicator mode={data.trading_mode} />
          <div className="grid gap-4 lg:grid-cols-2">
            <Card
              title="Trading configuration"
              subtitle="Defaults are paper-safe. Live requires full gating checklist."
            >
              <Row label="Trading mode" value={data.trading_mode.toUpperCase()} />
              <Row
                label="Live trading enabled"
                value={data.live_trading_enabled ? "true" : "false"}
              />
              <Row
                label="Kill switch"
                value={data.kill_switch_enabled ? "ACTIVE" : "clear"}
              />
              <Row label="Exchange env" value={data.exchange_env} />
              <Row label="Exchange id" value={data.exchange_id} />
              <Row
                label="Market data stale (s)"
                value={String(data.market_data_stale_seconds)}
              />
              <div className="mt-3 flex flex-wrap gap-1.5">
                {data.supported_symbols.map((s) => (
                  <Badge key={s} tone="accent">
                    {s}
                  </Badge>
                ))}
                {data.supported_timeframes.map((t) => (
                  <Badge key={t} tone="neutral">
                    {t}
                  </Badge>
                ))}
              </div>
              <p className="mt-4 border border-terminal-border/80 bg-terminal-muted/30 p-3 text-[11px] text-terminal-dim">
                This console intentionally omits any &quot;go live&quot; action. Live
                promotion is a separate gated process outside the dashboard.
              </p>
            </Card>

            <Card title="Risk limits" subtitle="Read-only snapshot from configuration">
              <Row
                label="Max risk / trade"
                value={formatPct(data.risk_limits.max_risk_per_trade)}
              />
              <Row
                label="Max position exposure"
                value={formatPct(data.risk_limits.max_position_exposure)}
              />
              <Row
                label="Max portfolio exposure"
                value={formatPct(data.risk_limits.max_portfolio_exposure)}
              />
              <Row
                label="Max open positions"
                value={String(data.risk_limits.max_open_positions)}
              />
              <Row
                label="Max daily loss"
                value={formatPct(data.risk_limits.max_daily_loss)}
              />
              <Row
                label="Max drawdown"
                value={formatPct(data.risk_limits.max_drawdown)}
              />
              <Row
                label="Max consecutive losses"
                value={String(data.risk_limits.max_consecutive_losses)}
              />
              <Row
                label="Max orders / minute"
                value={String(data.risk_limits.max_orders_per_minute)}
              />
              <Row
                label="Min order notional"
                value={`$${data.risk_limits.min_order_notional}`}
              />
              <Row
                label="Default leverage"
                value={`${data.risk_limits.default_leverage}x`}
              />
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
