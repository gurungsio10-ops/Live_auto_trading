"use client";

import { MoneyValue } from "./MoneyValue";

/** P&L with sign colouring + accessible non-colour cue. */
export function PnlValue({
  value,
  compact = false,
  size = "md",
  className = "",
}: {
  value: string | number;
  compact?: boolean;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}) {
  const n = typeof value === "string" ? Number(value) : value;
  const cue = !Number.isFinite(n) || n === 0 ? "" : n > 0 ? "+" : "";

  return (
    <span className={`inline-flex min-w-0 items-baseline gap-1 ${className}`}>
      {cue ? (
        <span className="sr-only">{n > 0 ? "profit" : "loss"}</span>
      ) : null}
      <MoneyValue value={value} compact={compact} signed size={size} />
    </span>
  );
}
