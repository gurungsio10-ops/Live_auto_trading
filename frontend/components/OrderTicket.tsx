"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api-client";
import type { Order, OrderSide, OrderType } from "@/lib/types";
import { Button } from "@/components/ui/Button";

const symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"];

export function OrderTicket({
  onSubmitted,
}: {
  onSubmitted?: (order: Order) => void;
}) {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [side, setSide] = useState<OrderSide>("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [quantity, setQuantity] = useState("0.01");
  const [price, setPrice] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setMessage(null);
    try {
      const res = await api.post<Order>("/api/orders", {
        symbol,
        side,
        order_type: orderType,
        quantity,
        price: orderType === "limit" ? price : undefined,
        strategy_name: "manual",
      });
      setMessage(`Order ${res.data.id} → ${res.data.status}`);
      onSubmitted?.(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order failed");
    } finally {
      setPending(false);
    }
  }

  const field =
    "w-full border border-terminal-border bg-terminal-bg px-2 py-1.5 text-xs text-terminal-text outline-none focus:border-terminal-accent font-mono";

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <label className="block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
          Symbol
          <select
            className={`${field} mt-1`}
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          >
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
          Side
          <select
            className={`${field} mt-1`}
            value={side}
            onChange={(e) => setSide(e.target.value as OrderSide)}
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </label>
        <label className="block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
          Type
          <select
            className={`${field} mt-1`}
            value={orderType}
            onChange={(e) => setOrderType(e.target.value as OrderType)}
          >
            <option value="market">Market</option>
            <option value="limit">Limit</option>
          </select>
        </label>
        <label className="block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
          Quantity
          <input
            className={`${field} mt-1`}
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            required
          />
        </label>
        {orderType === "limit" && (
          <label className="col-span-2 block text-[10px] uppercase tracking-[0.12em] text-terminal-dim">
            Limit price
            <input
              className={`${field} mt-1`}
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              required
            />
          </label>
        )}
      </div>
      <Button type="submit" variant="primary" disabled={pending} className="w-full">
        {pending ? "Submitting…" : "Submit paper order"}
      </Button>
      {message && <p className="text-[11px] text-terminal-accent font-mono">{message}</p>}
      {error && <p className="text-[11px] text-terminal-loss font-mono">{error}</p>}
    </form>
  );
}
