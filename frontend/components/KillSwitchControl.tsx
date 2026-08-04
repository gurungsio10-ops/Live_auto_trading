"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

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
    const next = !active;
    const ok = window.confirm(
      next
        ? "Activate the kill switch?\n\nThis halts all new paper order submissions until deactivated."
        : "Deactivate the kill switch?\n\nNew paper orders may be submitted again subject to risk checks.",
    );
    if (!ok) return;

    setPending(true);
    setError(null);
    try {
      const res = await api.post<{ kill_switch_enabled: boolean }>("/api/kill-switch", {
        enabled: next,
      });
      onChanged?.(res.data.kill_switch_enabled);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kill switch update failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card
      title="Kill switch"
      subtitle="Protected control — confirmation required"
      actions={
        <Badge tone={active ? "danger" : "accent"}>
          {active ? "ACTIVE — HALTED" : "ARMED / CLEAR"}
        </Badge>
      }
    >
      <p className="text-[12px] leading-relaxed text-terminal-dim">
        Halts all new order submissions when active. Kept away from the mobile bottom bar to
        reduce accidental taps.
      </p>
      <div className="mt-4">
        <Button
          variant={active ? "secondary" : "danger"}
          disabled={pending}
          onClick={toggle}
          type="button"
          className="w-full sm:w-auto"
        >
          {pending ? "Updating…" : active ? "Deactivate kill switch" : "Activate kill switch"}
        </Button>
      </div>
      {error && (
        <p className="mt-2 text-[11px] font-mono text-terminal-loss" role="alert">
          {error}
        </p>
      )}
    </Card>
  );
}
