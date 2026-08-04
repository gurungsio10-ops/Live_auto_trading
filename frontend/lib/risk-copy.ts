import type { RiskReasonCode } from "@/lib/types";

export type RiskExplanation = {
  title: string;
  summary: string;
  recovery: string;
};

const COPY: Partial<Record<RiskReasonCode, RiskExplanation>> = {
  DATABASE_UNHEALTHY: {
    title: "Trading paused",
    summary:
      "Database health could not be confirmed, so Atlas rejected the cycle for safety.",
    recovery: "Check PostgreSQL connectivity, run migrations, then retry a paper cycle.",
  },
  RECONCILIATION_UNHEALTHY: {
    title: "Trading paused",
    summary:
      "Portfolio reconciliation found an inconsistency, so new risk approvals are blocked.",
    recovery: "Open Recovery / run reconciliation, fix the root cause, then clear the halt.",
  },
  MARKET_DATA_UNHEALTHY: {
    title: "Market data unavailable",
    summary: "Fresh market data was missing or stale, so the order was not approved.",
    recovery: "Verify market-data connectivity and candle freshness, then retry.",
  },
  RISK_ENGINE_UNHEALTHY: {
    title: "Risk engine unavailable",
    summary: "The risk engine could not validate the order safely.",
    recovery: "Inspect backend logs and restart the API if needed.",
  },
  KILL_SWITCH_ACTIVE: {
    title: "Kill switch active",
    summary: "All new order submissions are halted by the kill switch.",
    recovery: "Confirm conditions are safe, then deactivate the kill switch from Overview.",
  },
  LIVE_TRADING_DISABLED: {
    title: "Live trading blocked",
    summary: "Atlas is paper-only. Live money paths remain hard-blocked.",
    recovery: "Continue in paper mode. Do not enable live trading.",
  },
  DAILY_LOSS_LIMIT_REACHED: {
    title: "Daily loss limit reached",
    summary: "Further risk was rejected to protect the paper account.",
    recovery: "Wait for the next session day or adjust risk limits carefully in Settings.",
  },
  MAX_DRAWDOWN_REACHED: {
    title: "Max drawdown reached",
    summary: "Drawdown exceeded the configured limit, so the cycle was rejected.",
    recovery: "Review positions and risk limits before resuming paper trading.",
  },
  DATA_STALE: {
    title: "Stale market data",
    summary: "The latest candle was too old for a safe decision.",
    recovery: "Refresh market data or wait for the next candle update.",
  },
};

const FALLBACK: RiskExplanation = {
  title: "Risk decision",
  summary: "Atlas applied a risk control before any simulated fill.",
  recovery: "Review the reason code and message, then retry when conditions are healthy.",
};

export function explainRiskReason(code: string | null | undefined): RiskExplanation {
  if (!code) return FALLBACK;
  return COPY[code as RiskReasonCode] ?? {
    ...FALLBACK,
    title: code.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase()),
  };
}

export function reasonCodeTone(
  code: string | null | undefined,
): "neutral" | "accent" | "gain" | "loss" | "warn" | "danger" {
  if (!code || code === "OK") return "accent";
  if (
    code.includes("UNHEALTHY") ||
    code === "KILL_SWITCH_ACTIVE" ||
    code === "CIRCUIT_BREAKER_OPEN"
  ) {
    return "danger";
  }
  if (code.includes("REDUCED") || code.includes("STALE") || code.includes("LIMIT")) {
    return "warn";
  }
  if (code === "APPROVED" || code === "OK") return "gain";
  return "loss";
}
