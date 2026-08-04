"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { SectionCard } from "@/components/ui/SectionCard";
import { TimestampValue } from "@/components/values";
import type { TradeSignal } from "@/lib/types";

function directionTone(d: string) {
  const x = d.toLowerCase();
  if (x === "buy") return "positive" as const;
  if (x === "sell" || x === "exit") return "negative" as const;
  if (x === "hold") return "warning" as const;
  return "neutral" as const;
}

export function DecisionCard({
  signal,
  riskDecision,
  riskCode,
  execution,
}: {
  signal: TradeSignal;
  riskDecision?: string | null;
  riskCode?: string | null;
  execution?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const conf = signal.confidence?.trim();
  const showConfidence = conf && conf !== "0" && conf !== "0.0" && Number(conf) > 0;

  return (
    <SectionCard
      title="Latest strategy decision"
      description="Deterministic strategy output reviewed by the risk engine"
      actions={<Badge tone={directionTone(signal.direction)}>{signal.direction}</Badge>}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-lg font-semibold text-foreground">{signal.symbol}</p>
        <TimestampValue value={signal.timestamp} relative />
      </div>
      <dl className="mt-4 grid grid-cols-1 gap-3 text-[14px] sm:grid-cols-2">
        <div>
          <dt className="text-secondary">Strategy</dt>
          <dd className="font-medium text-foreground">{signal.strategy_name}</dd>
        </div>
        <div>
          <dt className="text-secondary">Source type</dt>
          <dd className="font-medium text-foreground">Strategy decision</dd>
        </div>
        {showConfidence ? (
          <div>
            <dt className="text-secondary">Confidence</dt>
            <dd className="font-medium text-foreground">{conf}</dd>
          </div>
        ) : null}
        <div>
          <dt className="text-secondary">Risk check</dt>
          <dd className="font-medium text-foreground">{riskDecision ?? "Not available"}</dd>
        </div>
        <div>
          <dt className="text-secondary">Execution</dt>
          <dd className="font-medium text-foreground">{execution ?? "Not available"}</dd>
        </div>
        {riskCode ? (
          <div>
            <dt className="text-secondary">Reason code</dt>
            <dd className="font-mono text-[13px] text-foreground">{riskCode}</dd>
          </div>
        ) : null}
      </dl>
      <p className="mt-4 text-[14px] leading-relaxed text-secondary">
        {signal.entry_rationale || "No explanation provided for this decision."}
      </p>
      <button
        type="button"
        className="mt-3 min-h-touch text-[13px] font-medium text-foreground"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {open ? "Hide technical details" : "View full explanation"}
      </button>
      {open ? (
        <div className="mt-2 rounded-control border border-border bg-surface-raised/50 p-3 text-[13px] text-secondary">
          <p>Invalidation: {signal.invalidation_condition || "—"}</p>
          <p className="mt-1">Suggested entry: {signal.suggested_entry ?? "—"}</p>
          <p className="mt-1">Suggested stop: {signal.suggested_stop ?? "—"}</p>
          <p className="mt-1">Suggested target: {signal.suggested_target ?? "—"}</p>
          <p className="mt-1">Version: {signal.strategy_version}</p>
        </div>
      ) : null}
    </SectionCard>
  );
}
