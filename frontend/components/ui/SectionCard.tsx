import { HTMLAttributes, ReactNode } from "react";

export function SectionCard({
  title,
  description,
  actions,
  className = "",
  children,
  ...props
}: Omit<HTMLAttributes<HTMLElement>, "title"> & {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section
      className={[
        "min-w-0 rounded-card border border-border bg-surface p-4 md:p-5 animate-fade-in",
        className,
      ].join(" ")}
      {...props}
    >
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title ? (
              <h2 className="text-[17px] font-semibold tracking-tight text-foreground md:text-[18px]">
                {title}
              </h2>
            ) : null}
            {description ? (
              <p className="mt-1 text-[13px] leading-relaxed text-secondary">{description}</p>
            ) : null}
          </div>
          {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
        </header>
      )}
      {children}
    </section>
  );
}
