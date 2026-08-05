"use client";

import { formatSignedPnl, pnlTone, type DisplayCurrency } from "@/lib/format";

export function PnlValue({
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
  compact?: boolean;
}) {
  void compact;
  const display = formatSignedPnl(value, currency);
  const tone = pnlTone(value);
  const toneClass =
    tone === "gain" ? "text-positive" : tone === "loss" ? "text-negative" : "text-foreground";
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
      className={`inline-block max-w-full whitespace-nowrap tabular ${sizeClass} ${toneClass} ${className}`}
      title={display}
      aria-label={display}
    >
      {tone === "gain" ? <span className="sr-only">profit </span> : null}
      {tone === "loss" ? <span className="sr-only">loss </span> : null}
      {display}
    </span>
  );
}
