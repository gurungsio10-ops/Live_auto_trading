"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MOBILE_MORE_ICON, NAV_ITEMS, isNavActive } from "@/lib/nav";

export function MobileBottomNav({ onMore }: { onMore: () => void }) {
  const pathname = usePathname();
  const primary = NAV_ITEMS.filter((i) => i.mobilePrimary);

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background-secondary/95 backdrop-blur lg:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      aria-label="Primary"
    >
      <ul className="grid h-bottomnav grid-cols-5">
        {primary.map((item) => {
          const active = isNavActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <li key={item.key}>
              <Link
                href={item.href}
                className={[
                  "flex h-full flex-col items-center justify-center gap-0.5 text-[11px] font-medium",
                  active ? "text-brand" : "text-muted",
                ].join(" ")}
                aria-current={active ? "page" : undefined}
              >
                <Icon className="h-5 w-5" aria-hidden />
                <span>{item.shortLabel ?? item.label}</span>
              </Link>
            </li>
          );
        })}
        <li>
          <button
            type="button"
            onClick={onMore}
            className="flex h-full w-full flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-muted"
            aria-label="More"
          >
            <MOBILE_MORE_ICON className="h-5 w-5" aria-hidden />
            <span>More</span>
          </button>
        </li>
      </ul>
    </nav>
  );
}
