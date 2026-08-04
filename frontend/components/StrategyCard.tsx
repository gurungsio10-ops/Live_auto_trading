"use client";

import { useState } from "react";
import type { Strategy, StrategyGovernanceStatus } from "@/lib/types";
import { api } from "@/lib/api-client";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SectionCard } from "@/components/ui/SectionCard";

function statusTone(status: StrategyGovernanceStatus) {
  switch (status) {
    case "LIVE_APPROVED":
      return "live" as const;
    case "PAPER":
    case "TESTNET":
      return "primary" as const;
    case "VALIDATED":
      return "positive" as const;
    case "BACKTESTING":
      return "warning" as const;
    case "RETIRED":
      return "negative" as const;
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
    <SectionCard
      title={strategy.name}
      description={strategy.description}
      actions={
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={statusTone(strategy.governance_status)}>
            {strategy.governance_status}
          </Badge>
          <PaperTradingBadge />
          {strategy.selected ? <Badge tone="primary">Selected</Badge> : null}
          {strategy.running ? <Badge tone="positive">Running</Badge> : null}
        </div>
      }
    >
      <p className="font-mono text-xs text-muted">
        {strategy.strategy_id} · v{strategy.version} · {strategy.timeframe}
      </p>
      <p className="mt-2 text-sm text-secondary">
        {strategy.symbols.length ? strategy.symbols.join(", ") : "Symbols not available"}
      </p>

      {canPaperControl && Object.keys(params).length > 0 ? (
        <div className="mt-4 grid grid-cols-2 gap-2">
          {Object.entries(params).map(([key, value]) => (
            <label key={key} className="block text-xs text-muted">
              {key}
              <input
                className="input-field mt-1 font-mono text-sm"
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
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          disabled={!!pending || strategy.selected}
          onClick={() => void run("select")}
        >
          {pending === "select" ? "…" : "Select"}
        </Button>
        {canPaperControl ? (
          <>
            <Button
              type="button"
              variant="primary"
              disabled={!!pending || strategy.running}
              onClick={() => void run("start")}
            >
              {pending === "start" ? "…" : "Start paper"}
            </Button>
            <Button
              type="button"
              variant="warn"
              disabled={!!pending || !strategy.running}
              onClick={() => void run("stop")}
            >
              {pending === "stop" ? "…" : "Stop"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={!!pending}
              onClick={() => void run("params")}
            >
              {pending === "params" ? "…" : "Save paper params"}
            </Button>
          </>
        ) : null}
      </div>
      {error ? <p className="mt-2 text-sm text-negative">{error}</p> : null}
    </SectionCard>
  );
}
