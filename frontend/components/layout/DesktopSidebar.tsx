"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { DeveloperProfile } from "@/components/brand/DeveloperProfile";
import { BRAND } from "@/lib/brand";
import { NAV_ITEMS, isNavActive } from "@/lib/nav";

export function DesktopSidebar({
  systemLabel,
}: {
  systemLabel: string;
}) {
  const pathname = usePathname();
  const items = NAV_ITEMS.filter((i) => i.desktop);

  return (
    <aside className="hidden w-sidebar shrink-0 flex-col border-r border-border bg-background-secondary lg:flex">
      <div className="border-b border-border px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-control bg-primary-soft text-sm font-bold text-foreground">
          A
        </div>
        <p className="mt-3 text-lg font-bold tracking-tight text-foreground">{BRAND.name}</p>
        <p className="mt-1 text-[12px] leading-snug text-secondary">{BRAND.subtitle}</p>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Primary">
        {items.map((item) => {
          const active = isNavActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.key}
              href={item.href}
              className={[
                "flex min-h-touch items-center gap-3 rounded-control px-3 text-sm font-medium transition duration-ui",
                active
                  ? "bg-primary-soft text-brand"
                  : "text-secondary hover:bg-surface-hover hover:text-foreground",
              ].join(" ")}
              aria-current={active ? "page" : undefined}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="space-y-3 border-t border-border p-4">
        <PaperTradingBadge />
        <p className="text-[12px] text-secondary">
          Backend: <span className="text-foreground">{systemLabel}</span>
        </p>
        <DeveloperProfile compact />
      </div>
    </aside>
  );
}
