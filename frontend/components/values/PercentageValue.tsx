"use client";

import { formatPct, pnlTone } from "@/lib/format";

export function PercentageValue({
  value,
  signed = false,
  className = "",
  size = "md",
}: {
  value: string | number | null | undefined;
  signed?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  void size;
  const display = formatPct(value, 2, signed);
  const tone = signed ? pnlTone(value) : "flat";
  const toneClass =
    tone === "gain" ? "text-positive" : tone === "loss" ? "text-negative" : "text-foreground";
  return (
    <span className={`tabular ${toneClass} ${className}`} title={display} aria-label={display}>
      {display}
    </span>
  );
}
