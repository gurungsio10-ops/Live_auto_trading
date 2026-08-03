import { ReactNode } from "react";

const tones = {
  neutral: "border-terminal-border text-terminal-dim bg-terminal-muted/40",
  accent: "border-terminal-accent/40 text-terminal-accent bg-terminal-accent/10",
  gain: "border-terminal-gain/40 text-terminal-gain bg-terminal-gain/10",
  loss: "border-terminal-loss/40 text-terminal-loss bg-terminal-loss/10",
  warn: "border-terminal-warn/40 text-terminal-warn bg-terminal-warn/10",
  danger: "border-terminal-danger/50 text-terminal-danger bg-terminal-danger/15",
  live: "border-terminal-live text-white bg-terminal-live animate-pulse-live",
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
        "inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.12em] border",
        tones[tone],
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}
