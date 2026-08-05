"use client";

import Link from "next/link";
import { Menu, Bell, ShieldAlert } from "lucide-react";
import { StatusDot } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

type Props = {
  backendOk: boolean | null;
  killSwitchOn: boolean;
  onMenu: () => void;
};

export function MobileHeader({ backendOk, killSwitchOn, onMenu }: Props) {
  return (
    <header
      className="sticky top-0 z-30 border-b border-[var(--border)] bg-[var(--bg)]/95 backdrop-blur-md md:hidden"
      style={{ paddingTop: "env(safe-area-inset-top)" }}
    >
      <div className="flex h-14 items-center gap-2 px-3">
        <button
          type="button"
          onClick={onMenu}
          className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] text-[var(--text)]"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>

        <Link href="/" className="flex min-w-0 flex-1 items-center gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-black text-white shadow-[0_0_20px_rgba(59,130,246,0.35)]">
            A
          </span>
          <span className="min-w-0">
            <span className="block text-[15px] font-bold leading-tight tracking-wide text-[var(--text)]">
              ATLAS
            </span>
            <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--success)]">
              Paper Trading
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-1.5">
          <StatusDot
            tone={backendOk === false ? "danger" : backendOk ? "success" : "neutral"}
            label={backendOk === false ? "Backend down" : backendOk ? "Backend connected" : "Backend unknown"}
            pulse={backendOk === true}
          />
          {killSwitchOn ? (
            <Link
              href="/kill-switch"
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--danger)]/40 bg-[var(--danger-soft)] text-[var(--danger)]"
              aria-label="Kill switch is on — open controls"
              title="Kill switch ON"
            >
              <ShieldAlert className="h-5 w-5" aria-hidden />
            </Link>
          ) : (
            <Link
              href="/system-health"
              className={cn(
                "inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] text-[var(--text-muted)]"
              )}
              aria-label="Notifications and system status"
            >
              <Bell className="h-5 w-5" aria-hidden />
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
