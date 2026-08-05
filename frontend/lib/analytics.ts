/** Types for paper performance analytics (simulated fills only). */

export type ClosedTrade = {
  id: string;
  trade_id: string;
  strategy_name: string;
  symbol: string;
  trading_pair: string;
  side: string;
  entry_time: string;
  exit_time: string;
  entry_price: string;
  exit_price: string;
  quantity: string;
  fees: string;
  slippage: string;
  gross_pnl: string;
  net_pnl: string;
  roi_pct: string;
  duration_seconds: number;
  exit_reason: string;
  risk_score: string;
  market_regime: string;
  paper_session_id: string;
};

export type PerformanceMetrics = {
  current_balance: string;
  starting_balance: string;
  unrealised_pnl: string;
  realised_pnl: string;
  daily_pnl: string;
  weekly_pnl: string;
  monthly_pnl: string;
  roi_pct: string;
  win_rate: string;
  loss_rate: string;
  profit_factor: string;
  average_win: string;
  average_loss: string;
  largest_win: string;
  largest_loss: string;
  maximum_drawdown: string;
  consecutive_wins: number;
  consecutive_losses: number;
  average_holding_time: string;
  total_fees: string;
  total_simulated_volume: string;
  trade_count: number;
  open_position_count: number;
  kill_switch_enabled?: boolean;
  exposure?: string;
  risk_score?: string;
  equity_curve?: {
    balance_history: { time: string; equity: string; balance: string }[];
    drawdown_history: { time: string; drawdown: string }[];
    daily_return_history: { date: string; return_pct: string }[];
  };
  banner?: string;
};

export type StrategyRanking = {
  rank: number;
  strategy_name: string;
  trade_count: number;
  net_pnl: string;
  win_rate: string;
  total_fees: string;
  capital_allocation_proxy: string;
  avg_roi_pct: string;
};
