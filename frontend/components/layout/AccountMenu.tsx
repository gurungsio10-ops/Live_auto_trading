"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { OwnerAvatar } from "@/components/brand/OwnerAvatar";
import { DeveloperAttribution } from "@/components/brand/DeveloperAttribution";
import { Button } from "@/components/ui/Button";
import { BRAND } from "@/lib/brand";

export function AccountMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    fetch("/api/auth/session", { cache: "no-store" })
      .then((res) => res.json())
      .then((body) => {
        if (active) setUsername(body?.data?.username ?? null);
      })
      .catch(() => {
        if (active) setUsername(null);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  async function logout() {
    setPending(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      setOpen(false);
      router.replace("/login");
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="inline-flex min-h-11 min-w-11 items-center gap-2 rounded-sm border border-transparent px-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        onClick={() => setOpen((v) => !v)}
      >
        <OwnerAvatar size="sm" />
        <span className="hidden max-w-[8rem] truncate text-left text-[11px] font-mono text-terminal-dim md:inline">
          {username ?? "Account"}
        </span>
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-64 border border-terminal-border bg-terminal-panel p-3 shadow-terminal"
        >
          <div className="flex items-center gap-3 border-b border-terminal-border pb-3">
            <OwnerAvatar size="md" />
            <div className="min-w-0">
              <p className="truncate font-display text-sm text-terminal-text">
                {username ?? "Signed in"}
              </p>
              <p className="truncate text-[10px] text-terminal-dim">{BRAND.name}</p>
            </div>
          </div>
          <div className="mt-3 space-y-1">
            <Link
              href="/settings"
              role="menuitem"
              className="flex min-h-11 items-center px-2 text-xs uppercase tracking-wide text-terminal-dim hover:bg-terminal-muted/50 hover:text-terminal-text"
              onClick={() => setOpen(false)}
            >
              Settings / About
            </Link>
            <Button
              type="button"
              variant="ghost"
              className="w-full justify-start"
              onClick={logout}
              disabled={pending}
            >
              {pending ? "Signing out…" : "Sign out"}
            </Button>
          </div>
          <DeveloperAttribution className="mt-3 border-t border-terminal-border pt-3" />
        </div>
      ) : null}
    </div>
  );
}
