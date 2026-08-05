"use client";

import { formatQty } from "@/lib/format";

export function QuantityValue({
  value,
  className = "",
}: {
  value: string | number | null | undefined;
  className?: string;
}) {
  const display = formatQty(value);
  return (
    <span className={`tabular text-foreground ${className}`} title={display} aria-label={display}>
      {display}
    </span>
  );
}
