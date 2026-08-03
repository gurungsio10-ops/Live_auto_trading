"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
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

  return (
    <div className="w-full max-w-sm border border-terminal-border bg-terminal-panel/90 shadow-terminal animate-fade-up">
      <div className="border-b border-terminal-border px-6 py-5">
        <p className="font-display text-2xl tracking-[0.18em] text-terminal-accent">ATLAS</p>
        <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-terminal-dim">
          Trading terminal · secure sign-in
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4 px-6 py-6">
        <label className="block">
          <span className="text-[11px] uppercase tracking-[0.14em] text-terminal-dim">
            Username
          </span>
          <input
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="mt-1 w-full border border-terminal-border bg-terminal-elevated/60 px-3 py-2 text-sm text-terminal-text outline-none focus:border-terminal-accent"
            required
          />
        </label>
        <label className="block">
          <span className="text-[11px] uppercase tracking-[0.14em] text-terminal-dim">
            Password
          </span>
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full border border-terminal-border bg-terminal-elevated/60 px-3 py-2 text-sm text-terminal-text outline-none focus:border-terminal-accent"
            required
          />
        </label>
        {error && (
          <p className="border border-terminal-danger/50 bg-terminal-danger/10 px-3 py-2 text-[11px] text-terminal-loss font-mono">
            {error}
          </p>
        )}
        <Button type="submit" variant="primary" disabled={pending} className="w-full py-2">
          {pending ? "Signing in…" : "Sign in"}
        </Button>
        <p className="text-center text-[10px] text-terminal-dim">
          Demo credentials · <span className="text-terminal-text">admin</span> /{" "}
          <span className="text-terminal-text">atlas</span>
        </p>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center terminal-grid p-4">
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
