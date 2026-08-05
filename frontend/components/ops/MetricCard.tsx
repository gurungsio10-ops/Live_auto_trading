import type { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  hint,
  icon,
  className = "",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <article
      className={[
        "rounded-card border border-border bg-surface-raised/50 p-3.5 shadow-soft",
        className,
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</p>
        {icon ? <span className="text-muted">{icon}</span> : null}
      </div>
      <div className="mt-2 min-w-0 text-[18px] font-semibold tabular text-foreground md:text-[20px]">
        {value}
      </div>
      {hint ? <div className="mt-1 text-[12px] text-secondary">{hint}</div> : null}
    </article>
  );
}
