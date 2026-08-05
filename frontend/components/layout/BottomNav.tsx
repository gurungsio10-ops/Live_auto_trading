"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NavIcon } from "@/components/icons/NavIcons";
import { NAV_ITEMS, isNavActive } from "@/lib/nav";

export function BottomNav({ onMore }: { onMore: () => void }) {
  const pathname = usePathname();
  const primary = NAV_ITEMS.filter((i) => i.mobilePrimary);

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 border-t border-terminal-border bg-terminal-panel/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      aria-label="Primary"
    >
      <ul className="grid grid-cols-5">
        {primary.map((item) => {
          const active = isNavActive(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={[
                  "flex min-h-[56px] flex-col items-center justify-center gap-0.5 px-1 text-[10px] uppercase tracking-wide",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]",
                  active ? "text-terminal-accent" : "text-terminal-dim",
                ].join(" ")}
                aria-current={active ? "page" : undefined}
              >
                <NavIcon name={item.key} className="h-5 w-5" />
                <span className="truncate">{item.shortLabel ?? item.label}</span>
              </Link>
            </li>
          );
        })}
        <li>
          <button
            type="button"
            onClick={onMore}
            className="flex min-h-[56px] w-full flex-col items-center justify-center gap-0.5 px-1 text-[10px] uppercase tracking-wide text-terminal-dim focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
            aria-label="More navigation"
          >
            <NavIcon name="more" className="h-5 w-5" />
            <span>More</span>
          </button>
        </li>
      </ul>
    </nav>
  );
}
