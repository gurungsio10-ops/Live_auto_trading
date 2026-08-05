export type EngineState = "running" | "paused" | "stopped" | "starting" | "error" | "degraded";
export type SystemState = "online" | "degraded" | "offline" | "ok" | "running" | "paused";
export type RiskState = "safe" | "warning" | "blocked";

export type UnifiedStatus = {
  status?: string;
  trading_mode?: string;
  engine?: { state?: string; reasons?: string[] };
  system?: { state?: string; degraded_reasons?: string[] };
  degraded_reasons?: string[];
  kill_switch?: { enabled?: boolean; state?: string };
  scheduler?: {
    state?: string;
    enabled?: boolean;
    paused?: boolean;
    next_run_at?: string | null;
    last_run_at?: string | null;
    worker_running?: boolean;
  };
  market_data?: { ok?: boolean; label?: string; state?: string; mode?: string };
  database?: { ok?: boolean; latency_ms?: number | null; state?: string };
  timestamp?: string;
  last_successful_cycle?: Record<string, unknown> | null;
  active_strategy_count?: number;
};

export function mapEngineState(raw?: string | null): EngineState {
  const s = (raw || "").toUpperCase();
  if (s === "RUNNING") return "running";
  if (s === "PAUSED") return "paused";
  if (s === "STARTING") return "starting";
  if (s === "ERROR") return "error";
  if (s === "DEGRADED") return "degraded";
  return "stopped";
}

export function mapSystemState(raw?: string | null, degradedReasons?: string[]): SystemState {
  const s = (raw || "").toUpperCase();
  if (s === "DISCONNECTED" || s === "ERROR") return "offline";
  if (s === "DEGRADED" || (degradedReasons && degradedReasons.length > 0)) return "degraded";
  if (s === "RUNNING") return "running";
  if (s === "PAUSED") return "paused";
  if (s === "OK" || s === "ONLINE") return "online";
  return "degraded";
}

export function engineFromPortfolio(input: {
  trading_paused?: boolean;
  kill_switch_enabled?: boolean;
  strategyRunning?: boolean | null;
}): EngineState {
  if (input.kill_switch_enabled || input.trading_paused) return "paused";
  if (input.strategyRunning) return "running";
  return "stopped";
}

export function systemFromHealth(input: {
  backend_reachable?: boolean;
  demo?: boolean;
  backend_error?: string;
}): SystemState {
  if (input.backend_reachable === false) return "offline";
  if (input.demo) return "degraded";
  if (input.backend_error) return "degraded";
  if (input.backend_reachable) return "online";
  return "degraded";
}

export function riskFromPortfolio(input: {
  kill_switch_enabled?: boolean;
  trading_paused?: boolean;
  drawdown?: string | number;
  maxDrawdown?: string | number;
}): RiskState {
  if (input.kill_switch_enabled) return "blocked";
  if (input.trading_paused) return "warning";
  const dd = Number(input.drawdown ?? 0);
  const max = Number(input.maxDrawdown ?? 0);
  const ddPct = Math.abs(dd) <= 1 ? dd * 100 : dd;
  const maxPct = Math.abs(max) <= 1 && max !== 0 ? max * 100 : max;
  if (maxPct > 0 && ddPct / maxPct >= 0.8) return "warning";
  return "safe";
}

export const STATUS_LABEL: Record<string, string> = {
  running: "Running",
  paused: "Paused",
  stopped: "Stopped",
  starting: "Starting",
  error: "Error",
  degraded: "Degraded",
  online: "Online",
  offline: "Offline",
  ok: "OK",
  safe: "Safe",
  warning: "Warning",
  blocked: "Blocked",
};
