"use client";

import { useMemo, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { TimestampValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
import type { SettingsView, TradeSignal } from "@/lib/types";

export default function MarketsPage() {
  const settings = useAsyncData<SettingsView>("/api/settings");
  const signals = useAsyncData<TradeSignal[]>("/api/signals");
  const [q, setQ] = useState("");
  const [signalFilter, setSignalFilter] = useState("ALL");

  const rows = useMemo(() => {
    const symbols =
      settings.status === "success" ? settings.data.supported_symbols : [];
    const signalMap = new Map<string, TradeSignal>();
    if (signals.status === "success") {
      for (const s of signals.data) {
        if (!signalMap.has(s.symbol)) signalMap.set(s.symbol, s);
      }
    }
    return symbols
      .map((symbol) => {
        const signal = signalMap.get(symbol);
        return {
          symbol,
          signal: signal?.direction ?? "no signal",
          strategy: signal?.strategy_name ?? "Not available",
          updated: signal?.timestamp ?? null,
          source: "Paper market feed",
        };
      })
      .filter((r) => r.symbol.toLowerCase().includes(q.toLowerCase()))
      .filter((r) => signalFilter === "ALL" || r.signal === signalFilter);
  }, [settings, signals, q, signalFilter]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Markets"
        description="Review available symbols, latest prices and current strategy signals."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={settings.meta?.demo} backendError={settings.meta?.backend_error} />

      <SectionCard>
        <div className="flex flex-col gap-2 md:flex-row">
          <input
            className="min-h-touch flex-1 rounded-control border border-border bg-surface-raised px-3 text-foreground outline-none focus:border-primary"
            placeholder="Search markets"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search markets"
          />
          <select
            className="min-h-touch rounded-control border border-border bg-surface-raised px-3 text-foreground"
            value={signalFilter}
            onChange={(e) => setSignalFilter(e.target.value)}
            aria-label="Signal filter"
          >
            <option value="ALL">All signals</option>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
            <option value="hold">Hold</option>
            <option value="no signal">No signal</option>
          </select>
        </div>
        <p className="mt-3 text-[13px] text-secondary">
          Live prices are not available from the current backend. Symbols and strategy signals are shown when present.
        </p>
      </SectionCard>

      {(settings.status === "loading" || signals.status === "loading") && <LoadingState />}
      {settings.status === "error" && (
        <ErrorState title="Unable to load markets" message={settings.error} onRetry={settings.reload} />
      )}

      {settings.status === "success" &&
        (rows.length ? (
          <>
            <div className="space-y-3 md:hidden">
              {rows.map((r) => (
                <article key={r.symbol} className="rounded-card border border-border bg-surface p-4">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[15px] font-semibold text-foreground">{r.symbol}</p>
                    <Badge
                      tone={
                        r.signal === "buy"
                          ? "positive"
                          : r.signal === "sell"
                            ? "negative"
                            : r.signal === "hold"
                              ? "warning"
                              : "neutral"
                      }
                    >
                      {r.signal}
                    </Badge>
                  </div>
                  <p className="mt-2 text-[13px] text-muted">Price: Not available</p>
                  <p className="mt-1 text-[13px] text-secondary">
                    Updated {r.updated ? <TimestampValue value={r.updated} relative /> : "—"}
                  </p>
                  <p className="mt-2 text-[13px] text-secondary">Strategy · {r.strategy}</p>
                  <p className="text-[13px] text-muted">Source · {r.source}</p>
                </article>
              ))}
            </div>

            <div className="hidden overflow-x-auto rounded-card border border-border md:block">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="bg-surface-raised text-secondary">
                  <tr>
                    {["Market", "Price", "Change", "Signal", "Strategy", "Data source", "Updated", "Status"].map(
                      (h) => (
                        <th key={h} className="px-3 py-3 font-medium">
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.symbol} className="border-t border-border">
                      <td className="px-3 py-3 font-medium text-foreground">{r.symbol}</td>
                      <td className="px-3 py-3 text-muted">Not available</td>
                      <td className="px-3 py-3 text-muted">—</td>
                      <td className="px-3 py-3">
                        <Badge tone="neutral">{r.signal}</Badge>
                      </td>
                      <td className="px-3 py-3 text-secondary">{r.strategy}</td>
                      <td className="px-3 py-3 text-secondary">{r.source}</td>
                      <td className="px-3 py-3 text-muted">
                        {r.updated ? <TimestampValue value={r.updated} relative /> : "—"}
                      </td>
                      <td className="px-3 py-3">
                        <Badge tone="warning">Paper</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <EmptyState title="No markets found" description="No symbols match the selected filters." />
        ))}
    </div>
  );
}
