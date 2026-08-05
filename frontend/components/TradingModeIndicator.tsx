"use client";

import type { TradingMode } from "@/lib/types";

export function TradingModeIndicator({
  mode,
  className = "",
}: {
  mode: TradingMode;
  className?: string;
}) {
  const isLive = mode === "live";

  return (
    <div
      className={[
        "relative overflow-hidden border px-4 py-3 font-display tracking-[0.2em] uppercase",
        isLive
          ? "border-terminal-live bg-terminal-live text-white animate-pulse-live"
          : "border-terminal-accent/50 bg-terminal-accent/10 text-terminal-accent",
        className,
      ].join(" ")}
      role="status"
      aria-label={`Trading mode: ${mode}`}
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <p className="text-[10px] tracking-[0.28em] opacity-80">Trading mode</p>
          <p className="mt-1 text-[clamp(1.5rem,5vw,1.875rem)] font-semibold">
            {isLive ? "LIVE" : "PAPER TRADING"}
          </p>
        </div>
        <div className="text-[10px] font-mono tracking-normal normal-case opacity-90 sm:text-right">
          {isLive ? (
            <>
              <p className="font-bold">REAL CAPITAL AT RISK</p>
              <p>Live gating checklist must remain green</p>
            </>
          ) : (
            <>
              <p>Simulated fills only</p>
              <p>No exchange orders submitted</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
