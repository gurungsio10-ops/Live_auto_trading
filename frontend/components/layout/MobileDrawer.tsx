"use client";

import Link from "next/link";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { BrandMark } from "@/components/brand/BrandMark";
import { DeveloperAttribution } from "@/components/brand/DeveloperAttribution";
import { OwnerAvatar } from "@/components/brand/OwnerAvatar";
import { NavIcon } from "@/components/icons/NavIcons";
import { Badge } from "@/components/ui/Badge";
import { NAV_ITEMS, isNavActive } from "@/lib/nav";

export function MobileDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const items = NAV_ITEMS.filter((i) => i.mobileMore || i.desktop);

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
    <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="More">
      <button
        type="button"
        className="absolute inset-0 bg-black/60"
        aria-label="Close menu"
        onClick={onClose}
      />
      <aside className="absolute inset-y-0 right-0 flex w-[min(20rem,88vw)] flex-col border-l border-terminal-border bg-terminal-panel shadow-terminal">
        <div className="flex items-start justify-between gap-3 border-b border-terminal-border p-4">
          <BrandMark showPaperBadge size="sm" />
          <button
            type="button"
            className="inline-flex min-h-11 min-w-11 items-center justify-center text-terminal-dim"
            onClick={onClose}
            aria-label="Close"
          >
            <NavIcon name="close" />
          </button>
        </div>
        <div className="flex items-center gap-3 border-b border-terminal-border px-4 py-3">
          <OwnerAvatar size="md" />
          <div className="min-w-0">
            <p className="text-sm text-terminal-text">Account</p>
            <Badge tone="warn" className="mt-1">
              PAPER
            </Badge>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto p-2" aria-label="Secondary">
          {items.map((item) => {
            const active = isNavActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={[
                  "mb-0.5 flex min-h-11 items-center gap-3 px-3 text-xs font-display uppercase tracking-[0.12em]",
                  active
                    ? "border border-terminal-accent/40 bg-terminal-accent/10 text-terminal-accent"
                    : "border border-transparent text-terminal-dim hover:border-terminal-border hover:text-terminal-text",
                ].join(" ")}
                aria-current={active ? "page" : undefined}
              >
                <NavIcon name={item.icon} className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-terminal-border p-4">
          <DeveloperAttribution showAvatar />
        </div>
      </aside>
    </div>
  );
}
