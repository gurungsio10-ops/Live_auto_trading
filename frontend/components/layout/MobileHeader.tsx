"use client";

import { Bell, Circle } from "lucide-react";
import { BRAND } from "@/lib/brand";

export function MobileHeader({
  title,
  systemOnline,
}: {
  title: string;
  systemOnline: boolean;
}) {
  return (
    <header className="sticky top-0 z-30 flex h-header items-center justify-between gap-3 border-b border-border bg-background/95 px-4 backdrop-blur lg:hidden pt-[env(safe-area-inset-top)]">
      <div className="flex min-w-0 items-center gap-2">
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-control bg-primary-soft text-xs font-bold text-foreground">
          A
        </span>
        <div className="min-w-0">
          <p className="truncate text-[11px] text-muted">{BRAND.shortName}</p>
          <p className="truncate text-sm font-semibold text-foreground">{title}</p>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <span
          className="inline-flex min-h-touch min-w-touch items-center justify-center"
          title={systemOnline ? "System online" : "System offline"}
          aria-label={systemOnline ? "System online" : "System offline"}
        >
          <Circle
            className={`h-3 w-3 fill-current ${systemOnline ? "text-positive" : "text-negative"}`}
          />
        </span>
        <button
          type="button"
          className="inline-flex min-h-touch min-w-touch items-center justify-center text-secondary"
          aria-label="Notifications"
          title="Notifications are not configured"
        >
          <Bell className="h-5 w-5" />
        </button>
      </div>
    </header>
  );
}
