"use client";

import type { RiskDecision, RiskEvent } from "@/lib/types";
import { formatTs } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, Td } from "@/components/ui/Table";

function decisionTone(d: RiskDecision) {
  switch (d) {
    case "APPROVED":
      return "gain" as const;
    case "REJECTED":
      return "loss" as const;
    case "REDUCED":
      return "warn" as const;
    case "HALTED":
      return "danger" as const;
  }
}

export function RiskEventLog({ events }: { events: RiskEvent[] }) {
  if (!events.length) {
    return (
      <EmptyState
        title="No risk events"
        description="APPROVED / REJECTED / REDUCED / HALTED decisions with reason codes appear here."
      />
    );
  }

  return (
    <Table
      headers={[
        "Time",
        "Decision",
        "Reason code",
        "Symbol",
        "Strategy",
        "Qty",
        "Message",
      ]}
    >
      {events.map((e) => (
        <tr key={e.id} className="hover:bg-terminal-muted/40">
          <Td className="text-terminal-dim whitespace-nowrap">{formatTs(e.timestamp)}</Td>
          <Td mono={false}>
            <Badge tone={decisionTone(e.decision)}>{e.decision}</Badge>
          </Td>
          <Td>
            <span className="border border-terminal-border bg-terminal-muted/50 px-1.5 py-0.5 text-[10px] tracking-wide">
              {e.reason_code}
            </span>
          </Td>
          <Td className="text-terminal-accent">{e.symbol ?? "—"}</Td>
          <Td>{e.strategy_name ?? "—"}</Td>
          <Td>
            {e.requested_quantity ?? "—"}
            {e.approved_quantity && e.approved_quantity !== e.requested_quantity
              ? ` → ${e.approved_quantity}`
              : ""}
          </Td>
          <Td className="max-w-xs truncate text-terminal-dim" mono={false}>
            {e.message}
          </Td>
        </tr>
      ))}
    </Table>
  );
}
