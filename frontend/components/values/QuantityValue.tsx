"use client";

import { formatQty, formatQtyAsset } from "@/lib/format";

export function QuantityValue({
  value,
  asset,
  digits = 6,
  className = "",
}: {
  value: string | number;
  asset?: string;
  digits?: number;
  className?: string;
}) {
  const display = asset ? formatQtyAsset(value, asset, digits) : formatQty(value, digits);
  return (
    <span
      className={`inline-block whitespace-nowrap font-mono tabular-nums text-sm text-terminal-text ${className}`}
      title={display}
      aria-label={display}
    >
      {display}
    </span>
  );
}
