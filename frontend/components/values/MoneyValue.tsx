"use client";

import { formatCompactMoney, formatMoney, pnlTone } from "@/lib/format";

type Props = {
  value: string | number;
  currency?: "USD" | "GBP";
  compact?: boolean;
  /** Colorize by sign (for P&L-like amounts). */
  signed?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
};

const sizes = {
  sm: "text-xs",
  md: "text-sm",
  lg: "text-[clamp(0.95rem,2.8vw,1.125rem)]",
  xl: "text-[clamp(1.1rem,3.5vw,1.5rem)]",
};

export function MoneyValue({
  value,
  currency = "USD",
  compact = false,
  signed = false,
  className = "",
  size = "md",
}: Props) {
  const full = formatMoney(value, 2, currency);
  const display = compact ? formatCompactMoney(value, currency) : full;
  const tone = signed ? pnlTone(value) : "flat";
  const toneClass =
    tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-terminal-text";

  return (
    <span
      className={[
        "inline-block max-w-full min-w-0 whitespace-nowrap font-mono tabular-nums tracking-tight",
        sizes[size],
        toneClass,
        className,
      ].join(" ")}
      title={full}
      aria-label={full}
    >
      {display}
    </span>
  );
}
