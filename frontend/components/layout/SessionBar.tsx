"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";

export function SessionBar() {
  const router = useRouter();
  const [username, setUsername] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

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

  async function logout() {
    setPending(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      router.replace("/login");
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <div className="hidden text-right text-[10px] text-terminal-dim font-mono sm:block">
        <p>
          Signed in as{" "}
          <span className="text-terminal-text">{username ?? "…"}</span>
        </p>
        <p>No client-side secrets</p>
      </div>
      <Button variant="ghost" onClick={logout} disabled={pending} type="button">
        {pending ? "…" : "Sign out"}
      </Button>
    </div>
  );
}
