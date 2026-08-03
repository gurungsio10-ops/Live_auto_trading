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
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-[10px] tracking-[0.28em] opacity-80">Trading mode</p>
          <p className="mt-1 text-2xl font-semibold sm:text-3xl">
            {isLive ? "LIVE" : "PAPER"}
          </p>
        </div>
        <div className="text-right text-[10px] font-mono tracking-normal normal-case opacity-90">
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
