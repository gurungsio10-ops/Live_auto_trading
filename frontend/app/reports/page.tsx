"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";

type Period = "daily" | "weekly" | "monthly";

export default function ReportsPage() {
  const [period, setPeriod] = useState<Period>("daily");
  const report = useAsyncData<Record<string, unknown>>(
    `/api/analytics/reports/${period}`,
  );
  const [msg, setMsg] = useState<string | null>(null);

  async function download(format: "json" | "csv", kind: "trades" | "report") {
    setMsg(null);
    try {
      const path =
        kind === "trades"
          ? `/api/analytics/export/trades?format=${format}`
          : `/api/analytics/export/report/${period}?format=${format}`;
      if (format === "csv") {
        const res = await fetch(path, { cache: "no-store" });
        if (!res.ok) throw new Error(`Export failed (${res.status})`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download =
          kind === "trades"
            ? `paper_trades.csv`
            : `paper_report_${period}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        const res = await api.get<Record<string, unknown>>(path);
        const blob = new Blob([JSON.stringify(res.data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download =
          kind === "trades"
            ? `paper_trades.json`
            : `paper_report_${period}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
      setMsg(`Downloaded ${kind} (${format})`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Export failed");
    }
  }

  return (
    <div className="min-w-0 space-y-4" data-testid="reports-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl tracking-[0.08em] uppercase">
            Reports
          </h1>
          <p className="mt-1 text-xs text-terminal-dim">
            Automatic paper performance reports — CSV / JSON export.
          </p>
        </div>
        <Badge tone="accent">PAPER ONLY</Badge>
      </div>

      <Card title="Period">
        <div className="flex flex-wrap gap-2">
          {(["daily", "weekly", "monthly"] as Period[]).map((p) => (
            <Button
              key={p}
              variant={period === p ? "primary" : "ghost"}
              onClick={() => setPeriod(p)}
            >
              {p}
            </Button>
          ))}
        </div>
      </Card>

      <Card title={`${period} report`}>
        {report.status === "loading" ? (
          <p className="text-xs text-terminal-dim">Generating…</p>
        ) : null}
        {report.status === "error" ? (
          <p className="text-xs text-terminal-danger">{report.error}</p>
        ) : null}
        {report.status === "success" ? (
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] text-terminal-dim">
            {JSON.stringify(report.data, null, 2)}
          </pre>
        ) : null}
      </Card>

      <Card title="Export">
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => download("json", "report")}>Report JSON</Button>
          <Button onClick={() => download("csv", "report")}>Report CSV</Button>
          <Button onClick={() => download("json", "trades")}>Trades JSON</Button>
          <Button onClick={() => download("csv", "trades")}>Trades CSV</Button>
        </div>
        {msg ? <p className="mt-3 text-xs font-mono text-terminal-dim">{msg}</p> : null}
      </Card>
    </div>
  );
}
