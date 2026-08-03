"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { SessionBar } from "./SessionBar";

// Routes that render without the dashboard chrome (sidebar/header).
const BARE_ROUTES = ["/login"];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  if (BARE_ROUTES.includes(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen terminal-grid">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-terminal-border bg-terminal-bg/90 px-4 py-3 backdrop-blur scanlines">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.16em] text-terminal-text">
              Operations console
            </p>
            <p className="text-[11px] text-terminal-dim font-mono">
              Dense · dark · risk-first · paper by default
            </p>
          </div>
          <SessionBar />
        </header>
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
