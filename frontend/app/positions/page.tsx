"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Briefcase } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { PositionCard } from "@/components/cards/PositionCard";
import { SegmentTabs } from "@/components/ops/SegmentTabs";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import type { Position } from "@/lib/types";

type Tab = "open" | "closed";

export default function PositionsPage() {
  const positions = useAsyncData<Position[]>("/api/positions");
  const [tab, setTab] = useState<Tab>("open");
  const [closing, setClosing] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const openCount = positions.status === "success" ? positions.data.length : 0;

  async function closePosition(symbol: string) {
    setClosing(symbol);
    try {
      await api.post("/api/positions/close", { symbol });
      await positions.reload();
      setMsg(`Closed paper position ${symbol}`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Close failed");
    } finally {
      setClosing(null);
    }
  }

  const tabs = useMemo(
    () => [
      { id: "open" as const, label: "Open", count: openCount },
      { id: "closed" as const, label: "Closed" },
    ],
    [openCount],
  );

  return (
    <div className="space-y-4">
      <PageHeader
        title="Positions"
        description="Open and closed paper positions from the simulated account."
        meta={<PaperTradingBadge />}
      />
      <PaperModeBanner />
      <DemoBanner demo={positions.meta?.demo} backendError={positions.meta?.backend_error} />
      {msg ? (
        <p className="text-[13px] text-info" role="status">
          {msg}
        </p>
      ) : null}

      <SegmentTabs tabs={tabs} value={tab} onChange={setTab} ariaLabel="Position tabs" />

      {tab === "open" && (
        <>
          {positions.status === "loading" && <LoadingState label="Loading positions…" />}
          {positions.status === "error" && (
            <ErrorState
              title="Unable to load positions"
              message={positions.error}
              onRetry={positions.reload}
            />
          )}
          {positions.status === "success" &&
            (positions.data.length ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {positions.data.map((p) => (
                  <PositionCard
                    key={`${p.symbol}-${p.opened_at}`}
                    position={p}
                    onClose={closePosition}
                    closing={closing === p.symbol}
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-card border border-dashed border-border bg-surface-raised/40 px-4 py-10 text-center">
                <Briefcase className="mx-auto h-10 w-10 text-muted" aria-hidden />
                <p className="mt-3 text-[15px] font-semibold text-foreground">No open positions</p>
                <p className="mx-auto mt-2 max-w-sm text-[13px] text-secondary">
                  The paper account currently has no active market exposure.
                </p>
                <Link
                  href="/signals"
                  className="mt-4 inline-flex min-h-touch items-center justify-center rounded-control bg-primary px-4 text-[13px] font-semibold text-white"
                >
                  View strategy signals
                </Link>
              </div>
            ))}
        </>
      )}

      {tab === "closed" && (
        <EmptyState
          title="Closed position history unavailable"
          description="The backend does not currently expose a closed-positions feed. Realised P&L remains on Overview and Portfolio."
        />
      )}
    </div>
  );
}
