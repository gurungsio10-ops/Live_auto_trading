"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { MoneyValue, PnlValue, QuantityValue, TimestampValue } from "@/components/values";
import type { Position } from "@/lib/types";

export function PositionCard({
  position,
  onClose,
  closing,
}: {
  position: Position;
  onClose?: (symbol: string) => void;
  closing?: boolean;
}) {
  const side = Number(position.quantity) >= 0 ? "LONG" : "SHORT";
  const exposure = Math.abs(Number(position.quantity) * Number(position.current_price));

  return (
    <article className="rounded-card border border-border bg-surface-raised/40 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[15px] font-semibold text-foreground">{position.symbol}</p>
          <p className="mt-0.5 text-[12px] text-muted">
            Opened <TimestampValue value={position.opened_at} relative />
          </p>
        </div>
        <Badge tone={side === "LONG" ? "positive" : "negative"}>{side}</Badge>
      </div>
      <div className="mt-3">
        <p className="text-[12px] text-muted">Unrealised P/L</p>
        <PnlValue value={position.unrealized_pnl} size="lg" />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-[13px]">
        <div>
          <p className="text-muted">Quantity</p>
          <QuantityValue value={Math.abs(Number(position.quantity))} />
        </div>
        <div>
          <p className="text-muted">Entry</p>
          <MoneyValue value={position.entry_price} size="sm" />
        </div>
        <div>
          <p className="text-muted">Current</p>
          <MoneyValue value={position.current_price} size="sm" />
        </div>
        <div>
          <p className="text-muted">Exposure</p>
          <MoneyValue value={Number.isFinite(exposure) ? exposure : null} size="sm" />
        </div>
        <div>
          <p className="text-muted">Stop loss</p>
          <MoneyValue value={position.stop_loss} size="sm" />
        </div>
        <div>
          <p className="text-muted">Take profit</p>
          <MoneyValue value={position.take_profit} size="sm" />
        </div>
      </div>
      {onClose ? (
        <Button
          type="button"
          variant="dangerOutline"
          className="mt-4 w-full"
          disabled={closing}
          onClick={() => {
            const ok = window.confirm(`Close paper position ${position.symbol}?`);
            if (ok) onClose(position.symbol);
          }}
        >
          {closing ? "Closing…" : "Close position"}
        </Button>
      ) : null}
    </article>
  );
}
