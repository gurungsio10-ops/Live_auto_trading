"use client";

import { useState } from "react";
import { PositionsTable } from "@/components/PositionsTable";
import { Card } from "@/components/ui/Card";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import type { Position } from "@/lib/types";

export default function PositionsPage() {
  const { status, data, error, meta, reload, setData } =
    useAsyncData<Position[]>("/api/positions");
  const [closing, setClosing] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function closePosition(symbol: string) {
    setClosing(symbol);
    setMsg(null);
    try {
      const res = await api.post<Position[]>("/api/positions/close", { symbol });
      setData(res.data);
      setMsg(`Closed paper position ${symbol}`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Close failed");
    } finally {
      setClosing(null);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase">Positions</h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Open paper positions with mark P&L and close controls.
        </p>
      </div>
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />
      {msg && <p className="text-[11px] font-mono text-terminal-accent">{msg}</p>}
      <Card title="Open positions">
        {status === "loading" && <LoadingState label="Loading positions…" />}
        {status === "error" && <ErrorState message={error} onRetry={reload} />}
        {status === "success" && (
          <PositionsTable
            positions={data}
            onClose={closePosition}
            closingSymbol={closing}
          />
        )}
      </Card>
    </div>
  );
}
