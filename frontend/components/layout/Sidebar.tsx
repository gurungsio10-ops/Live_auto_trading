"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const NAV_LINKS = [
  { href: "/", label: "Overview" },
  { href: "/recovery", label: "Recovery" },
  { href: "/positions", label: "Positions" },
  { href: "/orders", label: "Orders" },
  { href: "/fills", label: "Fills" },
  { href: "/signals", label: "Signals" },
  { href: "/risk-events", label: "Risk" },
  { href: "/strategies", label: "Strategies" },
  { href: "/backtests", label: "Backtests" },
  { href: "/settings", label: "Settings" },
] as const;

function navActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-56 shrink-0 flex-col border-r border-terminal-border bg-terminal-panel/95 md:flex">
      <div className="border-b border-terminal-border px-4 py-5">
        <p className="font-display text-xl tracking-[0.18em] text-terminal-accent">ATLAS</p>
        <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-terminal-dim">
          Trading terminal
        </p>
        <p className="mt-2 inline-flex border border-terminal-accent/30 bg-terminal-accent/10 px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-[0.14em] text-terminal-accent">
          Paper only
        </p>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2">
        {NAV_LINKS.map((link) => {
          const active = navActive(pathname, link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={[
                "px-3 py-2 text-xs font-display uppercase tracking-[0.12em] border transition",
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
      <div className="border-t border-terminal-border p-3 text-[10px] text-terminal-dim font-mono">
        Paper V1 · FastAPI proxy
      </div>
    </aside>
  );
}

/** Horizontal nav for narrow viewports (sidebar hidden below md). */
export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 overflow-x-auto border-b border-terminal-border bg-terminal-panel/90 px-2 py-2 md:hidden">
      {NAV_LINKS.map((link) => {
        const active = navActive(pathname, link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={[
              "shrink-0 px-2.5 py-1.5 text-[10px] font-display uppercase tracking-[0.1em] border",
              active
                ? "border-terminal-accent/40 bg-terminal-accent/10 text-terminal-accent"
                : "border-transparent text-terminal-dim",
            ].join(" ")}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
