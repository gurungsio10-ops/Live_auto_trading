"use client";

import { ReactNode, useState } from "react";
import { NavIcon } from "@/components/icons/NavIcons";

export function MobileRecordCard({
  title,
  subtitle,
  badges,
  primary,
  details,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  badges?: ReactNode;
  primary: ReactNode;
  details?: ReactNode;
  actions?: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <article className="min-w-0 border border-terminal-border bg-terminal-elevated/40 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-display text-sm text-terminal-text">{title}</div>
          {subtitle ? (
            <div className="mt-0.5 truncate text-[11px] text-terminal-dim">{subtitle}</div>
          ) : null}
        </div>
        {badges ? <div className="flex shrink-0 flex-wrap justify-end gap-1">{badges}</div> : null}
      </div>
      <div className="mt-3 min-w-0 space-y-1.5">{primary}</div>
      {details ? (
        <div className="mt-3">
          <button
            type="button"
            className="inline-flex min-h-11 min-w-11 items-center gap-1 text-[11px] uppercase tracking-wide text-terminal-dim focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <NavIcon name="chevron" className={`h-4 w-4 transition ${open ? "rotate-90" : ""}`} />
            {open ? "Hide details" : "Details"}
          </button>
          {open ? <div className="mt-2 space-y-1.5 border-t border-terminal-border/80 pt-2">{details}</div> : null}
        </div>
      ) : null}
      {actions ? <div className="mt-3 flex flex-wrap gap-2">{actions}</div> : null}
    </article>
  );
}

export function RecordRow({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-3 text-[11px]">
      <span className="shrink-0 text-terminal-dim">{label}</span>
      <span className="min-w-0 truncate text-right font-mono tabular-nums text-terminal-text">
        {value}
      </span>
    </div>
  );
}
