import { ReactNode } from "react";

const tones = {
  neutral: "bg-surface-hover text-secondary border-border",
  primary: "bg-primary-soft text-brand border-primary/30",
  positive: "bg-positive-soft text-positive border-positive/30",
  negative: "bg-negative-soft text-negative border-negative/30",
  warning: "bg-warning-soft text-warning border-warning/30",
  info: "bg-info-soft text-info border-info/30",
  // legacy aliases
  accent: "bg-primary-soft text-brand border-primary/30",
  gain: "bg-positive-soft text-positive border-positive/30",
  loss: "bg-negative-soft text-negative border-negative/30",
  warn: "bg-warning-soft text-warning border-warning/30",
  danger: "bg-negative-soft text-negative border-negative/30",
  live: "bg-negative-soft text-negative border-negative/40",
} as const;

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: keyof typeof tones;
  className?: string;
}) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.06em]",
        tones[tone],
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}

export function PaperTradingBadge({ className = "" }: { className?: string }) {
  return (
    <Badge tone="warning" className={className}>
      PAPER TRADING
    </Badge>
  );
}
