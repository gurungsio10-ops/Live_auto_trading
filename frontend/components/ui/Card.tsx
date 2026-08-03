import { HTMLAttributes, ReactNode } from "react";

export function Card({
  title,
  subtitle,
  actions,
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section
      className={[
        "border border-terminal-border bg-terminal-panel/90 shadow-terminal animate-fade-up",
        className,
      ].join(" ")}
      {...props}
    >
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-terminal-border px-4 py-3">
          <div className="min-w-0">
            {title && (
              <h2 className="font-display text-sm tracking-[0.08em] uppercase text-terminal-text">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="mt-1 text-[11px] text-terminal-dim leading-relaxed">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}
