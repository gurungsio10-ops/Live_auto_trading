import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
import type { SettingsView } from "@/lib/types";

export const dynamic = "force-dynamic";

type SafeConfig = {
  trading_mode?: string;
  live_trading_enabled?: boolean;
  kill_switch_enabled?: boolean;
  exchange_env?: string;
  exchange_id?: string;
  supported_symbols?: string[];
  supported_timeframes?: string[];
  market_data_stale_seconds?: number;
  max_risk_per_trade?: string | number;
  max_position_exposure?: string | number;
  max_portfolio_exposure?: string | number;
  max_open_positions?: number;
  max_daily_loss?: string | number;
  max_drawdown?: string | number;
  max_consecutive_losses?: number;
  max_orders_per_minute?: number;
  min_order_notional?: string | number;
  default_leverage?: string | number;
};

function fromSafeConfig(cfg: SafeConfig): SettingsView {
  const base = demoState.settings;
  return {
    trading_mode: (cfg.trading_mode as SettingsView["trading_mode"]) ?? base.trading_mode,
    live_trading_enabled: cfg.live_trading_enabled ?? base.live_trading_enabled,
    kill_switch_enabled: cfg.kill_switch_enabled ?? base.kill_switch_enabled,
    exchange_env: (cfg.exchange_env as SettingsView["exchange_env"]) ?? base.exchange_env,
    exchange_id: cfg.exchange_id ?? base.exchange_id,
    supported_symbols: cfg.supported_symbols ?? base.supported_symbols,
    supported_timeframes: cfg.supported_timeframes ?? base.supported_timeframes,
    market_data_stale_seconds:
      cfg.market_data_stale_seconds ?? base.market_data_stale_seconds,
    risk_limits: {
      max_risk_per_trade: String(cfg.max_risk_per_trade ?? base.risk_limits.max_risk_per_trade),
      max_position_exposure: String(
        cfg.max_position_exposure ?? base.risk_limits.max_position_exposure,
      ),
      max_portfolio_exposure: String(
        cfg.max_portfolio_exposure ?? base.risk_limits.max_portfolio_exposure,
      ),
      max_open_positions: cfg.max_open_positions ?? base.risk_limits.max_open_positions,
      max_daily_loss: String(cfg.max_daily_loss ?? base.risk_limits.max_daily_loss),
      max_drawdown: String(cfg.max_drawdown ?? base.risk_limits.max_drawdown),
      max_consecutive_losses:
        cfg.max_consecutive_losses ?? base.risk_limits.max_consecutive_losses,
      max_orders_per_minute:
        cfg.max_orders_per_minute ?? base.risk_limits.max_orders_per_minute,
      min_order_notional: String(
        cfg.min_order_notional ?? base.risk_limits.min_order_notional,
      ),
      default_leverage: String(cfg.default_leverage ?? base.risk_limits.default_leverage),
    },
  };
}

export async function GET() {
  try {
    // Prefer a dedicated settings endpoint; fall back to redacted /config/safe.
    try {
      const data = await backendFetch<SettingsView>("/settings");
      return NextResponse.json(envelope(data, false));
    } catch {
      const cfg = await backendFetch<SafeConfig>("/config/safe");
      return NextResponse.json(envelope(fromSafeConfig(cfg), false));
    }
  } catch (err) {
    return NextResponse.json(
      envelope(
        demoState.settings,
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
