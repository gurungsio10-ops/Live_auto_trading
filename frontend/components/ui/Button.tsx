import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost" | "warn";

const variants: Record<Variant, string> = {
  primary:
    "bg-terminal-accent text-black hover:brightness-110 border border-terminal-accent",
  secondary:
    "bg-terminal-elevated text-terminal-text border border-terminal-border hover:border-terminal-dim",
  danger:
    "bg-terminal-danger/15 text-terminal-danger border border-terminal-danger/50 hover:bg-terminal-danger/25",
  warn: "bg-terminal-warn/15 text-terminal-warn border border-terminal-warn/40 hover:bg-terminal-warn/25",
  ghost: "bg-transparent text-terminal-dim border border-transparent hover:text-terminal-text hover:border-terminal-border",
};

export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={[
        "inline-flex items-center justify-center gap-2 px-3 py-1.5 text-xs font-medium tracking-wide uppercase transition disabled:opacity-40 disabled:cursor-not-allowed font-mono",
        variants[variant],
        className,
      ].join(" ")}
      {...props}
    />
  );
}
