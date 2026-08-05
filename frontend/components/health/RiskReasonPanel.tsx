"use client";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { TimestampValue } from "@/components/values";
import { explainRiskReason, reasonCodeTone } from "@/lib/risk-copy";

export function RiskReasonPanel({
  code,
  message,
  timestamp,
  affectedAction,
}: {
  code: string | null | undefined;
  message?: string | null;
  timestamp?: string | null;
  affectedAction?: string | null;
}) {
  if (!code || code === "OK") return null;
  const copy = explainRiskReason(code);

  return (
    <Card title={copy.title} subtitle="Risk control explanation">
      <div className="space-y-3">
        <p className="text-sm leading-relaxed text-terminal-text">{copy.summary}</p>
        {message ? (
          <p className="text-[12px] leading-relaxed text-terminal-dim">{message}</p>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] uppercase tracking-wide text-terminal-dim">Reason code</span>
          <Badge tone={reasonCodeTone(code)}>{code}</Badge>
        </div>
        {timestamp ? (
          <p className="text-[11px] text-terminal-dim">
            When: <TimestampValue value={timestamp} />
          </p>
        ) : null}
        {affectedAction ? (
          <p className="text-[11px] text-terminal-dim">Affected action: {affectedAction}</p>
        ) : null}
        <p className="border border-terminal-border bg-terminal-bg/50 px-3 py-2 text-[11px] text-terminal-dim">
          Recommended: {copy.recovery}
        </p>
      </div>
    </Card>
  );
}
