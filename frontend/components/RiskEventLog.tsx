"use client";

import type { RiskDecision, RiskEvent } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, Td } from "@/components/ui/Table";
import { MobileRecordCard, RecordRow } from "@/components/data/MobileRecordCard";
import { QuantityValue, TimestampValue } from "@/components/values";
import { explainRiskReason, reasonCodeTone } from "@/lib/risk-copy";

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
    <>
      <div className="space-y-2 md:hidden">
        {events.map((e) => {
          const copy = explainRiskReason(e.reason_code);
          return (
            <MobileRecordCard
              key={e.id}
              title={e.symbol ?? "Portfolio"}
              subtitle={<TimestampValue value={e.timestamp} compact />}
              badges={
                <>
                  <Badge tone={decisionTone(e.decision)}>{e.decision}</Badge>
                  <Badge tone={reasonCodeTone(e.reason_code)}>{e.reason_code}</Badge>
                </>
              }
              primary={
                <>
                  <p className="text-[12px] leading-snug text-terminal-text">{copy.title}</p>
                  <p className="text-[11px] leading-snug text-terminal-dim">{copy.summary}</p>
                </>
              }
              details={
                <>
                  <RecordRow label="Strategy" value={e.strategy_name ?? "—"} />
                  <RecordRow
                    label="Qty"
                    value={
                      e.requested_quantity ? (
                        <QuantityValue value={e.requested_quantity} />
                      ) : (
                        "—"
                      )
                    }
                  />
                  <RecordRow label="Message" value={e.message || "—"} />
                  <p className="pt-1 text-[11px] text-terminal-dim">Recovery: {copy.recovery}</p>
                </>
              }
            />
          );
        })}
      </div>

      <div className="hidden md:block">
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
              <Td className="text-terminal-dim whitespace-nowrap">
                <TimestampValue value={e.timestamp} />
              </Td>
              <Td mono={false}>
                <Badge tone={decisionTone(e.decision)}>{e.decision}</Badge>
              </Td>
              <Td mono={false}>
                <Badge tone={reasonCodeTone(e.reason_code)}>{e.reason_code}</Badge>
              </Td>
              <Td className="text-terminal-accent">{e.symbol ?? "—"}</Td>
              <Td>{e.strategy_name ?? "—"}</Td>
              <Td>
                {e.requested_quantity ? <QuantityValue value={e.requested_quantity} /> : "—"}
                {e.approved_quantity && e.approved_quantity !== e.requested_quantity
                  ? ` → ${e.approved_quantity}`
                  : ""}
              </Td>
              <Td className="max-w-xs truncate text-terminal-dim" mono={false} title={e.message}>
                {e.message}
              </Td>
            </tr>
          ))}
        </Table>
      </div>
    </>
  );
}
