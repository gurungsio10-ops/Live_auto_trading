"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrandMark } from "@/components/brand/BrandMark";
import { DeveloperAttribution } from "@/components/brand/DeveloperAttribution";
import { NavIcon } from "@/components/icons/NavIcons";
import { Badge } from "@/components/ui/Badge";
import { NAV_ITEMS, isNavActive } from "@/lib/nav";

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const pathname = usePathname();
  const links = NAV_ITEMS.filter((l) => l.desktop);

  return (
    <aside
      className={[
        "hidden shrink-0 flex-col border-r border-terminal-border bg-terminal-panel/95 md:flex",
        collapsed ? "w-[4.25rem]" : "w-56",
      ].join(" ")}
    >
      <div className="border-b border-terminal-border px-3 py-4">
        {collapsed ? (
          <p className="text-center font-display text-sm tracking-[0.14em] text-terminal-accent">
            A
          </p>
        ) : (
          <BrandMark showSubtitle size="sm" />
        )}
        <div className={`mt-3 ${collapsed ? "flex justify-center" : ""}`}>
          <Badge tone="warn">{collapsed ? "P" : "PAPER"}</Badge>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 p-2" aria-label="Primary">
        {links.map((link) => {
          const active = isNavActive(pathname, link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              title={link.label}
              className={[
                "flex min-h-11 items-center gap-3 border px-3 text-xs font-display uppercase tracking-[0.12em] transition",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]",
                collapsed ? "justify-center px-2" : "",
                active
                  ? "border-terminal-accent/40 bg-terminal-accent/10 text-terminal-accent"
                  : "border-transparent text-terminal-dim hover:border-terminal-border hover:text-terminal-text",
              ].join(" ")}
              aria-current={active ? "page" : undefined}
            >
              <NavIcon name={link.key} className="h-4 w-4 shrink-0" />
              {!collapsed ? <span className="truncate">{link.label}</span> : null}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-terminal-border p-2">
        <button
          type="button"
          onClick={onToggle}
          className="flex min-h-11 w-full items-center justify-center gap-2 border border-terminal-border text-[10px] uppercase tracking-wide text-terminal-dim hover:text-terminal-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <NavIcon
            name="chevron"
            className={`h-4 w-4 transition ${collapsed ? "" : "rotate-180"}`}
          />
          {!collapsed ? <span>Collapse</span> : null}
        </button>
        {!collapsed ? <DeveloperAttribution className="mt-3 px-1" /> : null}
      </div>
    </aside>
  );
}
