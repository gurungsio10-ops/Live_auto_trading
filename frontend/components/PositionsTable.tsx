"use client";

import { useState } from "react";
import type { Position } from "@/lib/types";
import { formatMoney, formatQty, formatTs, pnlTone } from "@/lib/format";
import { Table, Td } from "@/components/ui/Table";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

function PositionCard({
  p,
  onClose,
  closingSymbol,
  expanded,
  onToggle,
}: {
  p: Position;
  onClose?: (symbol: string) => void;
  closingSymbol?: string | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  const uTone = pnlTone(p.unrealized_pnl);
  return (
    <article className="border border-terminal-border bg-terminal-elevated/40">
      <button
        type="button"
        onClick={onToggle}
        className="flex min-h-[44px] w-full items-center justify-between gap-3 px-3 py-3 text-left"
        aria-expanded={expanded}
      >
        <div className="min-w-0">
          <p className="truncate font-display text-sm text-terminal-accent">{p.symbol}</p>
          <p className="mt-0.5 text-[11px] font-mono text-terminal-dim">
            qty {formatQty(p.quantity)} · {p.strategy_name ?? "—"}
          </p>
        </div>
        <p
          className={[
            "shrink-0 font-mono tabular-nums text-sm",
            uTone === "gain" ? "text-gain" : uTone === "loss" ? "text-loss" : "",
          ].join(" ")}
        >
          {formatMoney(p.unrealized_pnl)}
        </p>
      </button>
      {expanded && (
        <dl className="space-y-2 border-t border-terminal-border/70 px-3 py-3 text-[11px] font-mono">
          <div className="flex justify-between gap-3">
            <dt className="text-terminal-dim">Entry</dt>
            <dd className="tabular-nums">{formatMoney(p.entry_price)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-terminal-dim">Mark</dt>
            <dd className="tabular-nums">{formatMoney(p.current_price)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-terminal-dim">Realized</dt>
            <dd className="tabular-nums">{formatMoney(p.realized_pnl)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-terminal-dim">Opened</dt>
            <dd className="truncate text-right">{formatTs(p.opened_at)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-terminal-dim">Stop / Target</dt>
            <dd className="tabular-nums">
              {p.stop_loss ? formatMoney(p.stop_loss) : "—"} /{" "}
              {p.take_profit ? formatMoney(p.take_profit) : "—"}
            </dd>
          </div>
          {onClose && (
            <Button
              variant="danger"
              type="button"
              className="mt-2 min-h-[44px] w-full"
              disabled={closingSymbol === p.symbol}
              onClick={() => onClose(p.symbol)}
            >
              {closingSymbol === p.symbol ? "Closing…" : "Close position"}
            </Button>
          )}
        </dl>
      )}
    </article>
  );
}

export function PositionsTable({
  positions,
  onClose,
  closingSymbol,
}: {
  positions: Position[];
  onClose?: (symbol: string) => void;
  closingSymbol?: string | null;
}) {
  const [openKey, setOpenKey] = useState<string | null>(null);

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
      {/* Mobile: expandable cards — never horizontal overflow */}
      <div className="space-y-2 md:hidden" data-testid="positions-cards">
        {positions.map((p) => {
          const key = `${p.symbol}-${p.opened_at}`;
          return (
            <PositionCard
              key={key}
              p={p}
              onClose={onClose}
              closingSymbol={closingSymbol}
              expanded={openKey === key}
              onToggle={() => setOpenKey(openKey === key ? null : key)}
            />
          );
        })}
      </div>

      {/* Desktop / tablet: dense table */}
      <div className="hidden md:block" data-testid="positions-table">
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
                      className="min-h-[44px]"
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
      </div>
    </>
  );
}
