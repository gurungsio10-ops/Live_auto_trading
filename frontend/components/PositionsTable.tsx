"use client";

import type { Position } from "@/lib/types";
import { formatMoney, formatQty, formatTs, pnlTone } from "@/lib/format";
import { Table, Td } from "@/components/ui/Table";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export function PositionsTable({
  positions,
  onClose,
  closingSymbol,
}: {
  positions: Position[];
  onClose?: (symbol: string) => void;
  closingSymbol?: string | null;
}) {
  if (!positions.length) {
    return (
      <EmptyState
        title="No open positions"
        description="Paper positions will appear here when a strategy is filled."
      />
    );
  }

  return (
    <Table
      headers={[
        "Symbol",
        "Qty",
        "Entry",
        "Mark",
        "uP&L",
        "rP&L",
        "Strategy",
        "Opened",
        "Stop",
        "Target",
        "",
      ]}
    >
      {positions.map((p) => {
        const uTone = pnlTone(p.unrealized_pnl);
        const rTone = pnlTone(p.realized_pnl);
        return (
          <tr key={`${p.symbol}-${p.opened_at}`} className="hover:bg-terminal-muted/40">
            <Td className="text-terminal-accent">{p.symbol}</Td>
            <Td>{formatQty(p.quantity)}</Td>
            <Td>{formatMoney(p.entry_price)}</Td>
            <Td>{formatMoney(p.current_price)}</Td>
            <Td
              className={
                uTone === "gain" ? "text-gain" : uTone === "loss" ? "text-loss" : ""
              }
            >
              {formatMoney(p.unrealized_pnl)}
            </Td>
            <Td
              className={
                rTone === "gain" ? "text-gain" : rTone === "loss" ? "text-loss" : ""
              }
            >
              {formatMoney(p.realized_pnl)}
            </Td>
            <Td>{p.strategy_name ?? "—"}</Td>
            <Td className="text-terminal-dim">{formatTs(p.opened_at)}</Td>
            <Td>{p.stop_loss ? formatMoney(p.stop_loss) : "—"}</Td>
            <Td>{p.take_profit ? formatMoney(p.take_profit) : "—"}</Td>
            <Td>
              {onClose && (
                <Button
                  variant="danger"
                  type="button"
                  disabled={closingSymbol === p.symbol}
                  onClick={() => onClose(p.symbol)}
                >
                  {closingSymbol === p.symbol ? "Closing…" : "Close"}
                </Button>
              )}
            </Td>
          </tr>
        );
      })}
    </Table>
  );
}
