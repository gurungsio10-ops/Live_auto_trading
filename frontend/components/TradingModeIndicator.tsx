"use client";

import type { TradingMode } from "@/lib/types";

export function TradingModeIndicator({
  mode,
  runtimeMode,
  exchangeEnv,
  className = "",
}: {
  mode: TradingMode;
  runtimeMode?: string;
  exchangeEnv?: string;
  className?: string;
}) {
  const resolved = (runtimeMode || (mode === "live" ? "LIVE" : "PAPER")).toUpperCase();
  const isLive = resolved === "LIVE" || mode === "live";
  const isTestnet = resolved === "TESTNET" || exchangeEnv === "testnet";

  return (
    <div
      className={[
        "relative overflow-hidden border px-4 py-3 font-display tracking-[0.2em] uppercase",
        isLive
          ? "border-terminal-live bg-terminal-live text-white animate-pulse-live"
          : isTestnet
            ? "border-amber-500/60 bg-amber-500/10 text-amber-200"
            : "border-terminal-accent/50 bg-terminal-accent/10 text-terminal-accent",
        className,
      ].join(" ")}
      role="status"
      aria-label={`Runtime mode: ${resolved}`}
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-[10px] tracking-[0.28em] opacity-80">Runtime mode</p>
          <p className="mt-1 text-2xl font-semibold sm:text-3xl">{resolved}</p>
        </div>
        <div className="text-right text-[10px] font-mono tracking-normal normal-case opacity-90">
          {isLive ? (
            <>
              <p className="font-bold">REAL CAPITAL AT RISK</p>
              <p>Live gating checklist must remain green</p>
            </>
          ) : isTestnet ? (
            <>
              <p className="font-bold">SPOT TESTNET — not live money</p>
              <p>Exchange sim funds only</p>
            </>
          ) : (
            <>
              <p className="font-bold">SIMULATED FILLS</p>
              <p>No live order routing</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
