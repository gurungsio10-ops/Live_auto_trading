"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview" },
  { href: "/positions", label: "Positions" },
  { href: "/orders", label: "Orders" },
  { href: "/fills", label: "Fills" },
  { href: "/signals", label: "Signals" },
  { href: "/risk-events", label: "Risk events" },
  { href: "/strategies", label: "Strategies" },
  { href: "/backtests", label: "Backtests" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-terminal-border bg-terminal-panel/95">
      <div className="border-b border-terminal-border px-4 py-5">
        <p className="font-display text-xl tracking-[0.18em] text-terminal-accent">ATLAS</p>
        <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-terminal-dim">
          Trading terminal
        </p>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 p-2">
        {links.map((link) => {
          const active =
            link.href === "/"
              ? pathname === "/"
              : pathname.startsWith(link.href);
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
        Phase 11 · FastAPI proxy
      </div>
    </aside>
  );
}
