"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DESKTOP_NAV, navActive } from "@/lib/nav";
import { AtlasFooter } from "./AtlasFooter";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      data-testid="desktop-sidebar"
      className="hidden w-56 shrink-0 flex-col border-r border-terminal-border bg-terminal-panel/95 lg:flex"
    >
      <div className="border-b border-terminal-border px-4 py-5">
        <p className="font-display text-xl tracking-[0.18em] text-terminal-accent">ATLAS</p>
        <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-terminal-dim">
          Trading terminal
        </p>
        <p className="mt-2 inline-flex border border-terminal-accent/30 bg-terminal-accent/10 px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-[0.14em] text-terminal-accent">
          Paper only · Live disabled
        </p>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2" aria-label="Desktop">
        {DESKTOP_NAV.map((link) => {
          const active = navActive(pathname, link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={[
                "min-h-[44px] px-3 py-2 text-xs font-display uppercase tracking-[0.12em] border transition flex items-center",
                active
                  ? "border-terminal-accent/40 bg-terminal-accent/10 text-terminal-accent"
                  : "border-transparent text-terminal-dim hover:border-terminal-border hover:text-terminal-text",
              ].join(" ")}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
      <AtlasFooter className="border-t border-terminal-border !px-3 !py-3 !text-left" />
    </aside>
  );
}
