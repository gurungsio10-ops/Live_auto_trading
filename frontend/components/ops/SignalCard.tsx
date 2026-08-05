import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { TimestampValue } from "@/components/values";
import type { TradeSignal } from "@/lib/types";

function directionTone(d: string) {
  const x = d.toLowerCase();
  if (x === "buy") return "positive" as const;
  if (x === "sell" || x === "exit") return "negative" as const;
  if (x === "hold") return "neutral" as const;
  return "neutral" as const;
}

function directionLabel(d: string) {
  const x = d.toLowerCase();
  if (x === "buy") return "BUY";
  if (x === "sell") return "SELL";
  if (x === "exit") return "EXIT";
  if (x === "hold") return "NEUTRAL";
  return d.toUpperCase();
}

export function SignalCard({
  signal,
  riskDecision,
  compact = false,
}: {
  signal: TradeSignal;
  riskDecision?: string | null;
  compact?: boolean;
}) {
  const conf = signal.confidence?.trim();
  const showConfidence = conf && conf !== "0" && conf !== "0.0" && Number(conf) > 0;

  return (
    <article className="rounded-card border border-border bg-surface-raised/40 p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[14px] font-semibold text-foreground">{signal.strategy_name}</p>
          <p className="mt-0.5 text-[13px] text-secondary">
            {signal.symbol}
            {signal.strategy_version ? ` · v${signal.strategy_version}` : ""}
          </p>
        </div>
        <Badge tone={directionTone(signal.direction)}>{directionLabel(signal.direction)}</Badge>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted">
        <TimestampValue value={signal.timestamp} relative />
        {showConfidence ? <span>Confidence {conf}</span> : null}
        {riskDecision ? <span>Risk {riskDecision}</span> : null}
      </div>
      {!compact && signal.entry_rationale ? (
        <p className="mt-2 line-clamp-2 text-[13px] text-secondary">{signal.entry_rationale}</p>
      ) : null}
    </article>
  );
}

export function SignalListHeader({ href = "/signals" }: { href?: string }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <h2 className="text-[15px] font-semibold text-foreground">Recent signals</h2>
      <Link href={href} className="min-h-touch text-[13px] font-semibold text-brand hover:underline">
        View all
      </Link>
    </div>
  );
}
