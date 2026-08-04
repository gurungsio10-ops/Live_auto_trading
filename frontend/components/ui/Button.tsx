import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost" | "warn";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary:
    "bg-terminal-accent text-black hover:brightness-110 active:brightness-95 border border-terminal-accent",
  secondary:
    "bg-terminal-elevated text-terminal-text border border-terminal-border hover:border-terminal-dim active:bg-terminal-muted",
  danger:
    "bg-terminal-danger/15 text-terminal-danger border border-terminal-danger/50 hover:bg-terminal-danger/25 active:bg-terminal-danger/30",
  warn: "bg-terminal-warn/15 text-terminal-warn border border-terminal-warn/40 hover:bg-terminal-warn/25 active:bg-terminal-warn/30",
  ghost:
    "bg-transparent text-terminal-dim border border-transparent hover:text-terminal-text hover:border-terminal-border active:bg-terminal-muted/40",
};

const sizes: Record<Size, string> = {
  sm: "min-h-9 px-3 py-1.5 text-[11px]",
  md: "min-h-11 px-3.5 py-2 text-xs",
  lg: "min-h-12 px-4 py-2.5 text-sm",
};

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
}) {
  return (
    <button
      className={[
        "inline-flex items-center justify-center gap-2 rounded-sm font-medium uppercase tracking-wide transition",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]",
        "disabled:cursor-not-allowed disabled:opacity-40 font-mono",
        variants[variant],
        sizes[size],
        className,
      ].join(" ")}
      {...props}
    />
  );
}
