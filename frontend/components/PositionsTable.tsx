"use client";

import type { Position } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { Table, Td } from "@/components/ui/Table";
import { MobileRecordCard, RecordRow } from "@/components/data/MobileRecordCard";
import { MoneyValue, PnlValue, QuantityValue, TimestampValue } from "@/components/values";

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
    <>
      {/* Mobile cards */}
      <div className="space-y-2 md:hidden">
        {positions.map((p) => (
          <MobileRecordCard
            key={`${p.symbol}-${p.opened_at}`}
            title={p.symbol}
            subtitle={p.strategy_name ?? "Paper position"}
            primary={
              <>
                <RecordRow label="Qty" value={<QuantityValue value={p.quantity} />} />
                <RecordRow label="uP&L" value={<PnlValue value={p.unrealized_pnl} compact />} />
                <RecordRow label="Mark" value={<MoneyValue value={p.current_price} compact />} />
              </>
            }
            details={
              <>
                <RecordRow label="Entry" value={<MoneyValue value={p.entry_price} />} />
                <RecordRow label="Realized" value={<PnlValue value={p.realized_pnl} />} />
                <RecordRow label="Opened" value={<TimestampValue value={p.opened_at} compact />} />
                <RecordRow
                  label="Stop"
                  value={p.stop_loss ? <MoneyValue value={p.stop_loss} /> : "—"}
                />
                <RecordRow
                  label="Target"
                  value={p.take_profit ? <MoneyValue value={p.take_profit} /> : "—"}
                />
              </>
            }
            actions={
              onClose ? (
                <Button
                  variant="danger"
                  type="button"
                  className="w-full"
                  disabled={closingSymbol === p.symbol}
                  onClick={() => {
                    const ok = window.confirm(`Close paper position ${p.symbol}?`);
                    if (ok) onClose(p.symbol);
                  }}
                >
                  {closingSymbol === p.symbol ? "Closing…" : "Close position"}
                </Button>
              ) : undefined
            }
          />
        ))}
      </div>

      {/* Desktop table */}
      <div className="hidden md:block">
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
          {positions.map((p) => (
            <tr key={`${p.symbol}-${p.opened_at}`} className="hover:bg-terminal-muted/40">
              <Td className="text-terminal-accent">{p.symbol}</Td>
              <Td>
                <QuantityValue value={p.quantity} />
              </Td>
              <Td>
                <MoneyValue value={p.entry_price} />
              </Td>
              <Td>
                <MoneyValue value={p.current_price} />
              </Td>
              <Td>
                <PnlValue value={p.unrealized_pnl} />
              </Td>
              <Td>
                <PnlValue value={p.realized_pnl} />
              </Td>
              <Td>{p.strategy_name ?? "—"}</Td>
              <Td>
                <TimestampValue value={p.opened_at} compact />
              </Td>
              <Td>{p.stop_loss ? <MoneyValue value={p.stop_loss} /> : "—"}</Td>
              <Td>{p.take_profit ? <MoneyValue value={p.take_profit} /> : "—"}</Td>
              <Td>
                {onClose && (
                  <Button
                    variant="danger"
                    type="button"
                    size="sm"
                    disabled={closingSymbol === p.symbol}
                    onClick={() => {
                      const ok = window.confirm(`Close paper position ${p.symbol}?`);
                      if (ok) onClose(p.symbol);
                    }}
                  >
                    {closingSymbol === p.symbol ? "Closing…" : "Close"}
                  </Button>
                )}
              </Td>
            </tr>
          ))}
        </Table>
      </div>
    </>
  );
}
