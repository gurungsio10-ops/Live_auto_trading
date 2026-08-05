"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { MobileBottomNav } from "./MobileBottomNav";
import { SessionBar } from "./SessionBar";
import { AtlasFooter } from "./AtlasFooter";

const BARE_ROUTES = ["/login"];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  if (BARE_ROUTES.includes(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen min-w-0 overflow-x-hidden terminal-grid">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden">
        <header className="sticky top-0 z-20 flex min-w-0 items-center justify-between gap-3 border-b border-terminal-border bg-terminal-bg/92 px-4 py-3 backdrop-blur-md scanlines">
          <div className="min-w-0">
            <p className="truncate font-display text-sm uppercase tracking-[0.16em] text-terminal-text">
              Operations console
            </p>
            <p className="truncate text-[11px] text-terminal-dim font-mono">
              Dense · dark · risk-first · paper by default
            </p>
          </div>
          <SessionBar />
        </header>
        <main className="min-w-0 flex-1 overflow-x-hidden p-4 pb-24 md:p-6 lg:pb-6">
          {children}
        </main>
        <AtlasFooter className="hidden lg:block" />
        <MobileBottomNav />
      </div>
    </div>
  );
}
