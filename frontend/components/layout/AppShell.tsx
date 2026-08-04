"use client";

import { ReactNode, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { BottomNav } from "./BottomNav";
import { MobileDrawer } from "./MobileDrawer";
import { AccountMenu } from "./AccountMenu";
import { Badge } from "@/components/ui/Badge";
import { BrandMark } from "@/components/brand/BrandMark";
import { NavIcon } from "@/components/icons/NavIcons";

const BARE_ROUTES = ["/login"];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (BARE_ROUTES.includes(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-dvh min-h-screen overflow-x-hidden terminal-grid">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-terminal-border bg-terminal-bg/90 backdrop-blur">
          <div className="flex items-center justify-between gap-3 px-3 py-2.5 sm:px-4">
            <div className="flex min-w-0 items-center gap-2 md:hidden">
              <button
                type="button"
                className="inline-flex min-h-11 min-w-11 items-center justify-center text-terminal-dim"
                aria-label="Open menu"
                onClick={() => setDrawerOpen(true)}
              >
                <NavIcon name="menu" />
              </button>
              <BrandMark showSubtitle={false} size="sm" />
            </div>
            <div className="hidden min-w-0 md:block">
              <p className="font-display text-sm uppercase tracking-[0.14em] text-terminal-text">
                Operations console
              </p>
              <p className="text-[11px] text-terminal-dim">
                Risk-first · paper by default · mobile-ready
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Badge tone="warn" className="hidden sm:inline-flex">
                PAPER
              </Badge>
              <AccountMenu />
            </div>
          </div>
        </header>
        <main className="min-w-0 flex-1 px-3 pb-24 pt-4 sm:px-4 md:p-6 md:pb-6">
          {children}
        </main>
      </div>
      <BottomNav onMore={() => setDrawerOpen(true)} />
      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
