export type EngineState = "running" | "paused" | "stopped";
export type SystemState = "online" | "degraded" | "offline";
export type RiskState = "safe" | "warning" | "blocked";

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
  if (input.backend_reachable === false || input.demo) return "offline";
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
  online: "Online",
  degraded: "Degraded",
  offline: "Offline",
  safe: "Safe",
  warning: "Warning",
  blocked: "Blocked",
};
