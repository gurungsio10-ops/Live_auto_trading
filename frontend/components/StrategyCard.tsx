"use client";

import { useState } from "react";
import type { Strategy, StrategyGovernanceStatus } from "@/lib/types";
import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

function statusTone(status: StrategyGovernanceStatus) {
  switch (status) {
    case "LIVE_APPROVED":
      return "live" as const;
    case "PAPER":
    case "TESTNET":
      return "accent" as const;
    case "VALIDATED":
      return "gain" as const;
    case "BACKTESTING":
      return "warn" as const;
    case "RETIRED":
      return "loss" as const;
    default:
      return "neutral" as const;
  }
}

export function StrategyCard({
  strategy,
  onUpdated,
}: {
  strategy: Strategy;
  onUpdated?: (s: Strategy) => void;
}) {
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [params, setParams] = useState(strategy.paper_params);

  const canPaperControl =
    strategy.governance_status === "PAPER" || strategy.governance_status === "TESTNET";

  async function run(action: "start" | "stop" | "select" | "params") {
    setPending(action);
    setError(null);
    try {
      if (action === "select") {
        const res = await api.post<Strategy>("/api/strategies/select", {
          strategy_id: strategy.strategy_id,
        });
        onUpdated?.(res.data);
      } else if (action === "params") {
        const res = await api.patch<Strategy>(
          `/api/strategies/${strategy.strategy_id}/params`,
          { paper_params: params },
        );
        onUpdated?.(res.data);
      } else {
        const res = await api.post<Strategy>(
          `/api/strategies/${strategy.strategy_id}/${action}`,
        );
        onUpdated?.(res.data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setPending(null);
    }
  }

  return (
    <article className="border border-terminal-border bg-terminal-panel/80 p-4 shadow-terminal animate-fade-up">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-display text-base tracking-wide text-terminal-text">
            {strategy.name}
          </h3>
          <p className="mt-1 font-mono text-[11px] text-terminal-dim">
            {strategy.strategy_id} · v{strategy.version} · {strategy.timeframe}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={statusTone(strategy.governance_status)}>
            {strategy.governance_status}
          </Badge>
          {strategy.selected && <Badge tone="accent">Selected</Badge>}
          {strategy.running && <Badge tone="gain">Running</Badge>}
        </div>
      </div>
      <p className="mt-3 text-xs text-terminal-dim leading-relaxed">{strategy.description}</p>
      <p className="mt-2 font-mono text-[11px] text-terminal-dim">
        {strategy.symbols.join(", ")}
      </p>

      {canPaperControl && Object.keys(params).length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2">
          {Object.entries(params).map(([key, value]) => (
            <label
              key={key}
              className="block text-[10px] uppercase tracking-[0.1em] text-terminal-dim"
            >
              {key}
              <input
                className="mt-1 w-full border border-terminal-border bg-terminal-bg px-2 py-1 font-mono text-xs text-terminal-text outline-none focus:border-terminal-accent"
                value={String(value)}
                onChange={(e) => {
                  const raw = e.target.value;
                  const num = Number(raw);
                  setParams((prev) => ({
                    ...prev,
                    [key]: raw === "" || Number.isNaN(num) ? raw : num,
                  }));
                }}
              />
            </label>
          ))}
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          disabled={!!pending || strategy.selected}
          onClick={() => run("select")}
        >
          {pending === "select" ? "…" : "Select"}
        </Button>
        {canPaperControl && (
          <>
            <Button
              type="button"
              variant="primary"
              disabled={!!pending || strategy.running}
              onClick={() => run("start")}
            >
              {pending === "start" ? "…" : "Start paper"}
            </Button>
            <Button
              type="button"
              variant="warn"
              disabled={!!pending || !strategy.running}
              onClick={() => run("stop")}
            >
              {pending === "stop" ? "…" : "Stop"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={!!pending}
              onClick={() => run("params")}
            >
              {pending === "params" ? "…" : "Save paper params"}
            </Button>
          </>
        )}
      </div>
      {error && <p className="mt-2 text-[11px] text-terminal-loss font-mono">{error}</p>}
    </article>
  );
}
