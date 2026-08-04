"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BrandMark } from "@/components/brand/BrandMark";
import { DeveloperAttribution } from "@/components/brand/DeveloperAttribution";
import { OwnerAvatar } from "@/components/brand/OwnerAvatar";
import { Button } from "@/components/ui/Button";
import { BRAND } from "@/lib/brand";

export function LoginForm({ showDevCredentials }: { showDevCredentials: boolean }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, remember }),
      });
      if (!res.ok) {
        const payload = (await res.json().catch(() => null)) as { error?: string } | null;
        throw new Error(payload?.error ?? `Login failed (${res.status})`);
      }
      router.replace(nextPath);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setPending(false);
    }
  }

  const fieldClass =
    "mt-1 w-full min-h-11 border border-terminal-border bg-[var(--elevated)] px-3 py-3 text-base text-terminal-text outline-none focus:border-terminal-accent focus-visible:ring-2 focus-visible:ring-[var(--focus)]";

  return (
    <div className="w-full max-w-md animate-fade-up border border-terminal-border bg-terminal-panel/95 shadow-terminal">
      <div className="border-b border-terminal-border px-5 py-6 sm:px-6">
        <BrandMark showPaperBadge size="lg" />
        <p className="mt-4 text-sm leading-relaxed text-terminal-dim">
          Secure sign-in to your personal paper-trading operations console.
        </p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4 px-5 py-6 sm:px-6" noValidate>
        <label className="block">
          <span className="text-[11px] uppercase tracking-[0.14em] text-terminal-dim">
            Username
          </span>
          <input
            name="username"
            autoComplete="username"
            inputMode="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className={fieldClass}
            required
            aria-required
          />
        </label>

        <label className="block">
          <span className="text-[11px] uppercase tracking-[0.14em] text-terminal-dim">
            Password
          </span>
          <div className="relative mt-1">
            <input
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${fieldClass} mt-0 pr-24`}
              required
              aria-required
            />
            <button
              type="button"
              className="absolute inset-y-0 right-0 min-h-11 min-w-11 px-3 text-[11px] uppercase tracking-wide text-terminal-dim hover:text-terminal-text"
              onClick={() => setShowPassword((v) => !v)}
              aria-pressed={showPassword}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
        </label>

        <label className="flex min-h-11 items-center gap-3 text-[12px] text-terminal-dim">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="h-4 w-4 accent-terminal-accent"
          />
          Remember me for 30 days
        </label>

        {error && (
          <p
            className="border border-terminal-danger/50 bg-terminal-danger/10 px-3 py-2 text-[12px] font-mono text-terminal-loss"
            role="alert"
          >
            {error}
          </p>
        )}

        <Button type="submit" variant="primary" disabled={pending} className="w-full" size="lg">
          {pending ? "Signing in…" : "Sign in"}
        </Button>

        {showDevCredentials ? (
          <p className="text-center text-[11px] text-terminal-dim">
            Development credentials · <span className="text-terminal-text">admin</span> /{" "}
            <span className="text-terminal-text">atlas</span>
          </p>
        ) : null}
      </form>

      <footer className="flex items-center justify-between gap-3 border-t border-terminal-border px-5 py-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <OwnerAvatar size="md" />
          <div className="min-w-0">
            <p className="truncate text-xs text-terminal-text">{BRAND.ownerName}</p>
            <DeveloperAttribution className="mt-0.5" />
          </div>
        </div>
      </footer>
    </div>
  );
}
