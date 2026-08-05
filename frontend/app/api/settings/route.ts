import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
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
  return {
    trading_mode: (cfg.trading_mode as SettingsView["trading_mode"]) ?? "paper",
    live_trading_enabled: cfg.live_trading_enabled ?? false,
    kill_switch_enabled: cfg.kill_switch_enabled ?? false,
    exchange_env: (cfg.exchange_env as SettingsView["exchange_env"]) ?? "paper",
    exchange_id: cfg.exchange_id ?? "bybit",
    supported_symbols: cfg.supported_symbols ?? ["BTC/USDT"],
    supported_timeframes: cfg.supported_timeframes ?? ["1m", "5m", "15m", "1h"],
    market_data_stale_seconds: cfg.market_data_stale_seconds ?? 30,
    risk_limits: {
      max_risk_per_trade: String(cfg.max_risk_per_trade ?? "0.01"),
      max_position_exposure: String(cfg.max_position_exposure ?? "0.20"),
      max_portfolio_exposure: String(cfg.max_portfolio_exposure ?? "0.80"),
      max_open_positions: cfg.max_open_positions ?? 3,
      max_daily_loss: String(cfg.max_daily_loss ?? "0.03"),
      max_drawdown: String(cfg.max_drawdown ?? "0.10"),
      max_consecutive_losses: cfg.max_consecutive_losses ?? 5,
      max_orders_per_minute: cfg.max_orders_per_minute ?? 10,
      min_order_notional: String(cfg.min_order_notional ?? "10"),
      default_leverage: String(cfg.default_leverage ?? "1"),
    },
  };
}

export async function GET() {
  try {
    try {
      const data = await backendFetch<SettingsView>("/settings");
      return NextResponse.json(envelope(data, false));
    } catch {
      const cfg = await backendFetch<SafeConfig>("/config/safe");
      return NextResponse.json(envelope(fromSafeConfig(cfg), false));
    }
  } catch (err) {
    return NextResponse.json(
      envelope(null, false, err instanceof Error ? err.message : "backend down"),
      { status: 503 },
    );
  }
}
