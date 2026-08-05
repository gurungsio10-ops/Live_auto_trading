"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BOTTOM_NAV, navActive } from "@/lib/nav";

/**
 * Fixed bottom navigation for viewports below the tablet (lg) breakpoint.
 * Touch targets ≥ 44×44 px. No "Go Live" control.
 */
export function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav
      data-testid="mobile-bottom-nav"
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-terminal-border bg-terminal-panel/95 backdrop-blur-md lg:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <ul className="mx-auto grid max-w-lg grid-cols-5">
        {BOTTOM_NAV.map((item) => {
          const active = navActive(pathname, item.href);
          return (
            <li key={item.href} className="min-w-0">
              <Link
                href={item.href}
                data-testid={`nav-${item.label.toLowerCase()}`}
                aria-current={active ? "page" : undefined}
                className={[
                  "flex min-h-[44px] min-w-[44px] flex-col items-center justify-center gap-0.5 px-1 py-2 text-center",
                  "font-display text-[10px] uppercase tracking-[0.12em] transition",
                  active
                    ? "text-terminal-accent"
                    : "text-terminal-dim hover:text-terminal-text",
                ].join(" ")}
              >
                <span
                  className={[
                    "h-1 w-1 rounded-full",
                    active ? "bg-terminal-accent" : "bg-transparent",
                  ].join(" ")}
                  aria-hidden
                />
                <span className="truncate">{item.short ?? item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
