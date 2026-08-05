"use client";

import { Card } from "@/components/ui/Card";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useAsyncData } from "@/lib/use-async-data";

type FillRow = {
  id: string;
  order_id: string;
  symbol: string;
  side: string;
  quantity: string;
  price: string;
  fee: string;
  timestamp: string;
  simulated?: boolean;
};

export default function FillsPage() {
  const fills = useAsyncData<{ items: FillRow[]; total: number }>("/api/fills");

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase text-terminal-text">
          Fills
        </h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Simulated paper fills from the risk-gated paper broker.
        </p>
      </div>
      <DemoBanner demo={fills.meta?.demo} backendError={fills.meta?.backend_error} />
      {fills.status === "loading" && <LoadingState label="Loading fills…" />}
      {fills.status === "error" && (
        <ErrorState message={fills.error} onRetry={fills.reload} />
      )}
      {fills.status === "success" && (
        <Card title="Recent fills" subtitle={`${fills.data.total} total`}>
          {fills.data.items.length === 0 ? (
            <EmptyState title="No fills yet" description="Run a paper cycle to generate simulated fills." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[11px] font-mono">
                <thead className="text-terminal-dim">
                  <tr>
                    <th className="py-2 pr-3">Time</th>
                    <th className="py-2 pr-3">Symbol</th>
                    <th className="py-2 pr-3">Side</th>
                    <th className="py-2 pr-3">Qty</th>
                    <th className="py-2 pr-3">Price</th>
                    <th className="py-2 pr-3">Fee</th>
                  </tr>
                </thead>
                <tbody>
                  {fills.data.items.map((f) => (
                    <tr key={f.id} className="border-t border-terminal-border/40">
                      <td className="py-2 pr-3">{f.timestamp}</td>
                      <td className="py-2 pr-3">{f.symbol}</td>
                      <td className="py-2 pr-3 uppercase">{f.side}</td>
                      <td className="py-2 pr-3">{f.quantity}</td>
                      <td className="py-2 pr-3">{f.price}</td>
                      <td className="py-2 pr-3">{f.fee}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
