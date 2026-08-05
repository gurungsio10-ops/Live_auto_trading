"use client";

import { useState } from "react";
import Link from "next/link";
import { Power } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDangerDialog } from "@/components/ui/ConfirmDangerDialog";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { useAsyncData } from "@/lib/use-async-data";
import { api } from "@/lib/api-client";
import { formatRelativeTime } from "@/lib/format";
import type { PortfolioSummary, RiskEvent } from "@/lib/types";

export default function KillSwitchPage() {
  const portfolio = useAsyncData<PortfolioSummary>("/api/portfolio");
  const events = useAsyncData<RiskEvent[]>("/api/risk-events");
  const [pending, setPending] = useState(false);
  const [dialog, setDialog] = useState<"on" | "off" | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const active =
    portfolio.status === "success" ? Boolean(portfolio.data.kill_switch_enabled) : null;

  const killEvents =
    events.status === "success"
      ? events.data.filter((e) => e.reason_code === "KILL_SWITCH_ACTIVE").slice(0, 8)
      : [];

  async function apply(next: boolean) {
    setPending(true);
    setErr(null);
    try {
      const res = await api.post<{ kill_switch_enabled: boolean }>("/api/kill-switch", {
        enabled: next,
      });
      if (portfolio.status === "success") {
        portfolio.setData({
          ...portfolio.data,
          kill_switch_enabled: res.data.kill_switch_enabled,
        });
      } else {
        await portfolio.reload();
      }
      setMsg(
        res.data.kill_switch_enabled
          ? "Kill switch is ON — all trading activity is blocked."
          : "Kill switch is OFF — paper trading allowed subject to risk controls.",
      );
      setDialog(null);
      await events.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Kill switch update failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Kill Switch"
        description="Emergency halt for all new paper order submissions."
        meta={<PaperTradingBadge />}
      />
      <PaperModeBanner />
      <DemoBanner demo={portfolio.meta?.demo} backendError={portfolio.meta?.backend_error} />

      {portfolio.status === "loading" && <LoadingState label="Loading kill switch state…" />}
      {portfolio.status === "error" && (
        <ErrorState title="Unable to load portfolio" message={portfolio.error} onRetry={portfolio.reload} />
      )}

      {active != null && (
        <section className="rounded-card border border-border bg-surface px-4 py-8 text-center shadow-soft">
          <div
            className={[
              "mx-auto flex h-24 w-24 items-center justify-center rounded-full border-2",
              active
                ? "border-negative/50 bg-negative-soft text-negative shadow-[0_0_40px_rgba(239,68,68,0.25)]"
                : "border-positive/50 bg-positive-soft text-positive shadow-[0_0_40px_rgba(34,197,94,0.25)]",
            ].join(" ")}
          >
            <Power className="h-10 w-10" aria-hidden />
          </div>
          <p
            className={[
              "mt-5 text-xl font-bold",
              active ? "text-negative" : "text-positive",
            ].join(" ")}
          >
            Kill Switch is {active ? "ON" : "OFF"}
          </p>
          <p className="mx-auto mt-2 max-w-md text-[14px] text-secondary">
            {active
              ? "All trading activity is blocked."
              : "Paper-trading activity is allowed subject to Atlas risk controls."}
          </p>
          <div className="mt-6 flex flex-col items-stretch justify-center gap-2 sm:flex-row sm:items-center">
            <Link
              href="/audit"
              className="inline-flex min-h-touch items-center justify-center rounded-control border border-border bg-surface-raised px-4 text-[13px] font-semibold text-foreground"
            >
              View logs
            </Link>
            {active ? (
              <Button type="button" variant="danger" onClick={() => setDialog("off")} disabled={pending}>
                Turn OFF Kill Switch
              </Button>
            ) : (
              <Button type="button" variant="danger" onClick={() => setDialog("on")} disabled={pending}>
                Turn ON Kill Switch
              </Button>
            )}
          </div>
          {msg ? (
            <p className="mt-4 text-[13px] text-info" role="status">
              {msg}
            </p>
          ) : null}
          {err ? (
            <p className="mt-4 text-[13px] text-negative" role="alert">
              {err}
            </p>
          ) : null}
        </section>
      )}

      <SectionCard title="Recent kill-switch events" description="From risk event log">
        {events.status === "loading" && <LoadingState />}
        {events.status === "error" && <ErrorState message={events.error} onRetry={events.reload} />}
        {events.status === "success" &&
          (killEvents.length ? (
            <ul className="space-y-2">
              {killEvents.map((e) => (
                <li key={e.id} className="rounded-control border border-border px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <Badge tone="negative">{e.decision}</Badge>
                    <span className="text-[12px] text-muted">{formatRelativeTime(e.timestamp)}</span>
                  </div>
                  <p className="mt-1 text-[13px] text-foreground">{e.message || e.reason_code}</p>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No kill-switch events recorded" />
          ))}
      </SectionCard>

      <ConfirmDangerDialog
        open={dialog === "on"}
        title="Activate kill switch?"
        description="This blocks all new paper order submissions until the kill switch is turned off. Admin-authorised server request only — no token is sent to the browser."
        confirmLabel="Turn ON"
        onClose={() => setDialog(null)}
        onConfirm={() => void apply(true)}
        pending={pending}
      />
      <ConfirmDangerDialog
        open={dialog === "off"}
        title="Turn OFF kill switch?"
        description="Disabling protection allows new paper orders subject to Atlas risk controls. Type DISABLE to confirm."
        confirmLabel="Turn OFF"
        requireText="DISABLE"
        onClose={() => setDialog(null)}
        onConfirm={() => void apply(false)}
        pending={pending}
      />
    </div>
  );
}
