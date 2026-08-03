"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

export function KillSwitchControl({
  active,
  onChanged,
}: {
  active: boolean;
  onChanged?: (next: boolean) => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    setPending(true);
    setError(null);
    try {
      const res = await api.post<{ kill_switch_enabled: boolean }>("/api/kill-switch", {
        enabled: !active,
      });
      onChanged?.(res.data.kill_switch_enabled);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kill switch update failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="border border-terminal-border bg-terminal-elevated/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-display text-xs uppercase tracking-[0.14em] text-terminal-text">
            Kill switch
          </p>
          <p className="mt-1 text-[11px] text-terminal-dim">
            Halts all new order submissions when active.
          </p>
        </div>
        <Badge tone={active ? "danger" : "accent"}>
          {active ? "ACTIVE — HALTED" : "ARMED / CLEAR"}
        </Badge>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          variant={active ? "secondary" : "danger"}
          disabled={pending}
          onClick={toggle}
          type="button"
        >
          {pending ? "Updating…" : active ? "Deactivate kill switch" : "Activate kill switch"}
        </Button>
      </div>
      {error && <p className="mt-2 text-[11px] text-terminal-loss font-mono">{error}</p>}
    </div>
  );
}
