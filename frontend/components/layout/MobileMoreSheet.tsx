"use client";

import Link from "next/link";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { DeveloperProfile } from "@/components/brand/DeveloperProfile";
import { BRAND } from "@/lib/brand";
import { NAV_ITEMS, isNavActive } from "@/lib/nav";

export function MobileMoreSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const items = NAV_ITEMS.filter((i) => i.mobileMore);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="More">
      <button type="button" className="absolute inset-0 bg-black/55" aria-label="Close" onClick={onClose} />
      <aside className="absolute inset-y-0 right-0 flex w-[min(20rem,90vw)] flex-col border-l border-border bg-surface shadow-soft">
        <div className="flex items-start justify-between gap-3 border-b border-border p-4">
          <div>
            <p className="text-lg font-bold text-foreground">{BRAND.name}</p>
            <p className="mt-1 text-[12px] text-secondary">{BRAND.subtitle}</p>
            <div className="mt-2">
              <PaperTradingBadge />
            </div>
          </div>
          <button
            type="button"
            className="inline-flex min-h-touch min-w-touch items-center justify-center text-secondary"
            onClick={onClose}
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto p-2">
          {items.map((item) => {
            const active = isNavActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.key}
                href={item.href}
                onClick={onClose}
                className={[
                  "mb-1 flex min-h-touch items-center gap-3 rounded-control px-3 text-sm font-medium",
                  active ? "bg-primary-soft text-brand" : "text-secondary hover:bg-surface-hover",
                ].join(" ")}
              >
                <Icon className="h-4 w-4" aria-hidden />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-4">
          <DeveloperProfile />
        </div>
      </aside>
    </div>
  );
}
