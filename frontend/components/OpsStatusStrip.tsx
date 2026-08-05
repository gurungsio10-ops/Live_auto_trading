"use client";

import { Badge } from "@/components/ui/Badge";

type Props = {
  runtimeMode?: string;
  exchangeEnv?: string;
  tradingMode?: string;
  backendConnected: boolean;
  backendLoading?: boolean;
  schedulerRunning?: boolean;
  killSwitchActive?: boolean;
  liveEnabled?: boolean;
};

/**
 * Compact operational badges required on mobile Home:
 * PAPER / TESTNET / LIVE DISABLED / backend / scheduler / kill switch.
 */
export function OpsStatusStrip({
  runtimeMode,
  exchangeEnv,
  tradingMode,
  backendConnected,
  backendLoading,
  schedulerRunning,
  killSwitchActive,
  liveEnabled = false,
}: Props) {
  const resolved = (runtimeMode || tradingMode || "PAPER").toUpperCase();
  const isTestnet = resolved === "TESTNET" || exchangeEnv === "testnet";
  const isLive = resolved === "LIVE";

  return (
    <div
      data-testid="ops-status-strip"
      className="flex min-w-0 flex-wrap items-center gap-1.5"
      role="status"
      aria-label="Operational status"
    >
      <Badge tone={isLive ? "danger" : isTestnet ? "warn" : "accent"}>
        {isLive ? "LIVE" : isTestnet ? "TESTNET" : "PAPER"}
      </Badge>
      <Badge tone={liveEnabled ? "danger" : "neutral"}>
        {liveEnabled ? "LIVE ENABLED" : "LIVE DISABLED"}
      </Badge>
      <Badge
        tone={
          backendLoading ? "neutral" : backendConnected ? "gain" : "danger"
        }
      >
        {backendLoading
          ? "BACKEND …"
          : backendConnected
            ? "BACKEND CONNECTED"
            : "BACKEND DISCONNECTED"}
      </Badge>
      <Badge tone={schedulerRunning ? "gain" : "neutral"}>
        {schedulerRunning ? "SCHEDULER RUNNING" : "SCHEDULER STOPPED"}
      </Badge>
      <Badge tone={killSwitchActive ? "danger" : "accent"}>
        {killSwitchActive ? "KILL SWITCH ACTIVE" : "KILL SWITCH CLEAR"}
      </Badge>
    </div>
  );
}
