"use client";

import type { TradeSignal } from "@/lib/types";
import { formatPct, formatTs } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";

function directionTone(d: TradeSignal["direction"]) {
  if (d === "buy") return "gain" as const;
  if (d === "sell" || d === "exit") return "loss" as const;
  return "neutral" as const;
}

export function SignalFeed({ signals }: { signals: TradeSignal[] }) {
  if (!signals.length) {
    return (
      <EmptyState
        title="No signals"
        description="Strategy signals will stream here as evaluations complete."
      />
    );
  }

  return (
    <ul className="divide-y divide-terminal-border border border-terminal-border">
      {signals.map((s) => (
        <li key={s.id} className="bg-terminal-panel/60 px-4 py-3 hover:bg-terminal-elevated/50">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge tone={directionTone(s.direction)}>{s.direction}</Badge>
              <span className="font-mono text-xs text-terminal-accent">{s.symbol}</span>
              <span className="font-mono text-[11px] text-terminal-dim">
                {s.strategy_name}@{s.strategy_version}
              </span>
            </div>
            <span className="font-mono text-[11px] text-terminal-dim">
              {formatTs(s.timestamp)}
            </span>
          </div>
          <p className="mt-2 text-xs text-terminal-text">{s.entry_rationale}</p>
          <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-terminal-dim font-mono">
            <span>conf {formatPct(s.confidence)}</span>
            <span>invalidation: {s.invalidation_condition}</span>
            {s.suggested_entry && <span>entry {s.suggested_entry}</span>}
            {s.suggested_stop && <span>stop {s.suggested_stop}</span>}
            {s.suggested_target && <span>target {s.suggested_target}</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}
