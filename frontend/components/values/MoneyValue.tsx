"use client";

import { formatMoney, type DisplayCurrency } from "@/lib/format";

export function MoneyValue({
  value,
  currency = "USD",
  className = "",
  size = "md",
  compact = false,
}: {
  value: string | number | null | undefined;
  currency?: DisplayCurrency;
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  /** Accepted for legacy callers; compact display uses formatMoney with same digits. */
  compact?: boolean;
}) {
  void compact;
  const display = formatMoney(value, currency);
  const sizeClass =
    size === "xl"
      ? "text-[clamp(1.875rem,5vw,2.75rem)] font-bold"
      : size === "lg"
        ? "text-[clamp(1.25rem,3vw,1.75rem)] font-semibold"
        : size === "sm"
          ? "text-sm font-medium"
          : "text-[20px] font-semibold";
  return (
    <span
      className={`inline-block max-w-full whitespace-nowrap tabular text-foreground ${sizeClass} ${className}`}
      title={display}
      aria-label={display}
    >
      {display}
    </span>
  );
}

export function PriceValue(props: Parameters<typeof MoneyValue>[0]) {
  return <MoneyValue {...props} />;
}
