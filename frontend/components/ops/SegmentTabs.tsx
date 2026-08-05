"use client";

import { cn } from "@/lib/utils";

export function SegmentTabs<T extends string>({
  tabs,
  value,
  onChange,
  ariaLabel,
}: {
  tabs: { id: T; label: string; count?: number }[];
  value: T;
  onChange: (id: T) => void;
  ariaLabel: string;
}) {
  return (
    <div
      className="flex gap-1 overflow-x-auto rounded-control border border-border bg-surface-raised/40 p-1"
      role="tablist"
      aria-label={ariaLabel}
    >
      {tabs.map((tab) => {
        const active = tab.id === value;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            className={cn(
              "min-h-10 flex-1 whitespace-nowrap rounded-[10px] px-3 text-[13px] font-semibold transition",
              active
                ? "bg-primary text-white shadow-soft"
                : "text-secondary hover:text-foreground"
            )}
          >
            {tab.label}
            {typeof tab.count === "number" ? (
              <span className="ml-1 opacity-80">({tab.count})</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
