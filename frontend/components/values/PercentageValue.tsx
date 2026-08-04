"use client";

import { formatPct, pnlTone } from "@/lib/format";

export function PercentageValue({
  value,
  signed = false,
  className = "",
  size = "md",
}: {
  value: string | number;
  signed?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const display = formatPct(value);
  const tone = signed ? pnlTone(value) : "flat";
  const toneClass =
    tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-terminal-text";
  const sizeClass = size === "sm" ? "text-xs" : size === "lg" ? "text-base" : "text-sm";

  return (
    <span
      className={`inline-block whitespace-nowrap font-mono tabular-nums ${sizeClass} ${toneClass} ${className}`}
      title={display}
      aria-label={display}
    >
      {display}
    </span>
  );
}
