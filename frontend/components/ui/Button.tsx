import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "dangerOutline" | "warn" | "ghost";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "bg-primary text-white hover:bg-primary-hover border border-transparent",
  secondary:
    "bg-surface-raised text-foreground border border-border hover:border-border-strong hover:bg-surface-hover",
  warn: "bg-transparent text-warning border border-warning/40 hover:bg-warning-soft",
  danger: "bg-negative-soft text-negative border border-negative/40 hover:bg-negative/20",
  dangerOutline: "bg-transparent text-negative border border-negative/45 hover:bg-negative-soft",
  ghost: "bg-transparent text-secondary border border-transparent hover:text-foreground hover:bg-surface-hover",
};

const sizes: Record<Size, string> = {
  sm: "min-h-11 px-3 text-xs",
  md: "min-h-touch px-4 text-sm",
  lg: "min-h-touch-lg px-5 text-sm md:text-[15px]",
};

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      className={[
        "inline-flex items-center justify-center gap-2 rounded-control font-medium transition duration-ui",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]",
        "disabled:cursor-not-allowed disabled:opacity-45",
        variants[variant],
        sizes[size],
        className,
      ].join(" ")}
      {...props}
    />
  );
}
