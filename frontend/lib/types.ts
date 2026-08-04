/** Domain types mirroring Project Atlas backend concepts. */

export type TradingMode = "paper" | "live";
export type ExchangeEnv = "paper" | "testnet" | "live" | "backtest";
export type RuntimeMode = "BACKTEST" | "PAPER" | "TESTNET" | "LIVE";

export type SignalDirection = "buy" | "sell" | "hold" | "exit";
export type OrderSide = "buy" | "sell";
export type OrderType = "market" | "limit";

export type OrderStatus =
  | "CREATED"
  | "RISK_PENDING"
  | "APPROVED"
  | "SUBMITTED"
  | "PARTIALLY_FILLED"
  | "FILLED"
  | "REJECTED"
  | "CANCELLED"
  | "EXPIRED"
  | "FAILED";

export type RiskDecision = "APPROVED" | "REJECTED" | "REDUCED" | "HALTED";

export type RiskReasonCode =
  | "OK"
  | "KILL_SWITCH_ACTIVE"
  | "LIVE_TRADING_DISABLED"
  | "LIVE_GATING_INCOMPLETE"
  | "DATA_STALE"
  | "DUPLICATE_ORDER"
  | "INVALID_PRICE"
  | "INVALID_QUANTITY"
  | "MIN_ORDER_SIZE"
  | "PRECISION_INVALID"
  | "MAX_RISK_PER_TRADE"
  | "MAX_POSITION_EXPOSURE"
  | "MAX_PORTFOLIO_EXPOSURE"
  | "MAX_OPEN_POSITIONS"
  | "DAILY_LOSS_LIMIT_REACHED"
  | "MAX_DRAWDOWN_REACHED"
  | "MAX_CONSECUTIVE_LOSSES"
  | "MAX_ORDER_FREQUENCY"
  | "CIRCUIT_BREAKER_OPEN"
  | "RISK_ENGINE_UNHEALTHY"
  | "MARKET_DATA_UNHEALTHY"
  | "DATABASE_UNHEALTHY"
  | "RECONCILIATION_UNHEALTHY"
  | "INVALID_CREDENTIALS"
  | "INVALID_LIVE_APPROVAL"
  | "NEWS_EXTREME_UNCERTAINTY"
  | "SIZE_REDUCED_BY_NEWS"
  | "SIZE_REDUCED_BY_RISK";

export type StrategyGovernanceStatus =
  | "DRAFT"
  | "BACKTESTING"
  | "VALIDATED"
  | "PAPER"
  | "TESTNET"
  | "LIVE_APPROVED"
  | "RETIRED";

export interface Position {
  symbol: string;
  quantity: string;
  entry_price: string;
  current_price: string;
  unrealized_pnl: string;
  realized_pnl: string;
  opened_at: string;
  strategy_name: string | null;
  stop_loss: string | null;
  take_profit: string | null;
}

export interface PortfolioSummary {
  cash_balance: string;
  equity: string;
  realized_pnl: string;
  unrealized_pnl: string;
  daily_pnl: string;
  peak_equity: string;
  drawdown: string;
  open_position_count: number;
  consecutive_losses: number;
  trading_mode: TradingMode;
  runtime_mode?: RuntimeMode | string;
  kill_switch_enabled: boolean;
  trading_enabled?: boolean;
  trading_paused: boolean;
  exchange_env: ExchangeEnv;
}

export interface SystemStatusPayload {
  health: Record<string, unknown>;
  ready: Record<string, unknown>;
  metrics: Record<string, unknown>;
  banner: string;
}

export interface EquityPoint {
  time: string;
  equity: string;
  drawdown: string;
}

export interface Order {
  id: string;
  client_order_id: string;
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: string;
  filled_quantity: string;
  price: string | null;
  average_fill_price: string | null;
  status: OrderStatus;
  strategy_name: string | null;
  risk_decision: RiskDecision | null;
  risk_reason_code: RiskReasonCode | null;
  created_at: string;
  updated_at: string;
  fees: string;
}

export interface TradeSignal {
  id: string;
  strategy_name: string;
  strategy_version: string;
  symbol: string;
  timestamp: string;
  direction: SignalDirection;
  confidence: string;
  entry_rationale: string;
  invalidation_condition: string;
  suggested_stop: string | null;
  suggested_target: string | null;
  suggested_entry: string | null;
}

export interface RiskEvent {
  id: string;
  timestamp: string;
  decision: RiskDecision;
  reason_code: RiskReasonCode;
  message: string;
  symbol: string | null;
  strategy_name: string | null;
  requested_quantity: string | null;
  approved_quantity: string | null;
  order_id: string | null;
}

export interface Strategy {
  strategy_id: string;
  name: string;
  version: string;
  governance_status: StrategyGovernanceStatus;
  description: string;
  running: boolean;
  selected: boolean;
  paper_params: Record<string, string | number | boolean>;
  symbols: string[];
  timeframe: string;
}

export interface BacktestRequest {
  strategy_id: string;
  symbol: string;
  timeframe: string;
  start: string;
  end: string;
  initial_cash?: string;
}

export interface BacktestMetrics {
  trade_count: number;
  total_return: string;
  net_return: string;
  win_rate: string;
  profit_factor: string;
  max_drawdown: string;
  sharpe: string;
  sortino: string;
  fees_paid: string;
  slippage_cost: string;
}

export interface BacktestReport {
  run_id: string;
  strategy_id: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  config: Record<string, unknown>;
  metrics: BacktestMetrics | null;
  json_report: Record<string, unknown> | null;
  markdown_report: string | null;
  error: string | null;
}

export interface RiskLimits {
  max_risk_per_trade: string;
  max_position_exposure: string;
  max_portfolio_exposure: string;
  max_open_positions: number;
  max_daily_loss: string;
  max_drawdown: string;
  max_consecutive_losses: number;
  max_orders_per_minute: number;
  min_order_notional: string;
  default_leverage: string;
}

export interface SettingsView {
  trading_mode: TradingMode;
  live_trading_enabled: boolean;
  kill_switch_enabled: boolean;
  exchange_env: ExchangeEnv;
  exchange_id: string;
  supported_symbols: string[];
  supported_timeframes: string[];
  risk_limits: RiskLimits;
  market_data_stale_seconds: number;
}

export interface HealthStatus {
  status: string;
  trading_mode: TradingMode;
  live_trading_enabled: boolean;
  kill_switch_enabled: boolean;
  exchange_env: ExchangeEnv;
  backend_reachable: boolean;
  demo_mode: boolean;
}

export interface OrderTicketPayload {
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: string;
  price?: string;
  stop_loss?: string;
  take_profit?: string;
  strategy_name?: string;
}

export interface ApiMeta {
  demo: boolean;
  backend_error?: string;
}

export type ApiEnvelope<T> = {
  data: T;
  meta: ApiMeta;
};
