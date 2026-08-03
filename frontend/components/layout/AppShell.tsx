"use client";

import { ReactNode } from "react";
import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
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
          <div className="hidden text-right text-[10px] text-terminal-dim font-mono sm:block">
            <p>UTC clock · risk engine gated</p>
            <p>No client-side secrets</p>
          </div>
        </header>
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
