"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronsLeft, ChevronsRight } from "lucide-react";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { DeveloperProfile } from "@/components/brand/DeveloperProfile";
import { BRAND } from "@/lib/brand";
import { NAV_ITEMS, isNavActive } from "@/lib/nav";
import { cn } from "@/lib/utils";

const DESKTOP_KEYS = new Set([
  "overview",
  "positions",
  "orders",
  "signals",
  "strategies",
  "backtests",
  "risk",
  "riskEvents",
  "journal",
  "killSwitch",
  "scheduler",
  "systemHealth",
  "settings",
  "markets",
  "activity",
  "paperTrading",
  "connection",
]);

export function DesktopSidebar({ systemLabel }: { systemLabel: string }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const items = NAV_ITEMS.filter((i) => i.desktop && DESKTOP_KEYS.has(i.key));

  return (
    <aside
      className={cn(
        "hidden shrink-0 flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)] transition-[width] lg:flex",
        collapsed ? "w-[4.5rem]" : "w-56"
      )}
    >
      <div className="border-b border-[var(--border)] px-4 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-black text-white">
            A
          </span>
          {!collapsed ? (
            <div className="min-w-0">
              <p className="text-sm font-bold tracking-wide text-[var(--text)]">{BRAND.name}</p>
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--success)]">
                Paper Trading
              </p>
            </div>
          ) : null}
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2" aria-label="Primary">
        {items.map((item) => {
          const active = isNavActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.key}
              href={item.href}
              title={item.label}
              className={cn(
                "flex min-h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium transition",
                collapsed && "justify-center px-0",
                active
                  ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
              )}
              aria-current={active ? "page" : undefined}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              {!collapsed ? <span>{item.label}</span> : null}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-2 border-t border-[var(--border)] p-3">
        {!collapsed ? (
          <>
            <PaperTradingBadge />
            <p className="text-[11px] text-[var(--text-muted)]">
              Backend: <span className="text-[var(--text)]">{systemLabel}</span>
            </p>
            <DeveloperProfile compact />
          </>
        ) : null}
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="flex min-h-9 w-full items-center justify-center gap-2 rounded-xl border border-[var(--border)] text-xs text-[var(--text-muted)] hover:bg-[var(--bg-hover)]"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
          {!collapsed ? "Collapse" : null}
        </button>
      </div>
    </aside>
  );
}
