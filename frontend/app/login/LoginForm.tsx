"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { DeveloperProfile } from "@/components/brand/DeveloperProfile";
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

  const field =
    "mt-2 w-full min-h-touch rounded-control border border-border bg-surface-raised px-3 text-base text-foreground outline-none focus:border-brand";

  return (
    <div className="w-full max-w-md animate-fade-in rounded-card border border-border bg-surface shadow-soft">
      <div className="border-b border-border px-5 py-6 sm:px-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-control bg-primary-soft text-sm font-bold text-brand">
          A
        </div>
        <h1 className="mt-4 text-[28px] font-bold tracking-tight text-foreground">{BRAND.name}</h1>
        <p className="mt-1 text-[14px] text-secondary">{BRAND.subtitle}</p>
        <div className="mt-3">
          <PaperTradingBadge />
        </div>
      </div>

      <form onSubmit={onSubmit} className="space-y-4 px-5 py-6 sm:px-6" noValidate>
        <label className="block text-[13px] text-secondary">
          Username
          <input
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className={field}
            required
          />
        </label>
        <label className="block text-[13px] text-secondary">
          Password
          <div className="relative">
            <input
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${field} pr-12`}
              required
            />
            <button
              type="button"
              className="absolute inset-y-0 right-0 mt-2 inline-flex min-h-touch min-w-touch items-center justify-center text-muted"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </label>
        <label className="flex min-h-touch items-center gap-3 text-[13px] text-secondary">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="h-4 w-4 accent-[var(--primary)]"
          />
          Remember me for 30 days
        </label>
        {error ? (
          <p className="rounded-control border border-negative/40 bg-negative-soft px-3 py-2 text-[13px] text-negative" role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" variant="primary" size="lg" className="w-full" disabled={pending}>
          {pending ? "Signing in…" : "Sign in"}
        </Button>
        {showDevCredentials ? (
          <p className="text-center text-[12px] text-muted">
            Development credentials · admin / atlas
          </p>
        ) : null}
      </form>

      <footer className="border-t border-border px-5 py-4 sm:px-6">
        <DeveloperProfile />
      </footer>
    </div>
  );
}
