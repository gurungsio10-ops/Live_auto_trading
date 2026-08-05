"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { MoneyValue } from "@/components/values";
import { useAsyncData } from "@/lib/use-async-data";
import type { HealthStatus, SettingsView } from "@/lib/types";

export default function ConnectionPage() {
  const health = useAsyncData<HealthStatus>("/api/health");
  const settings = useAsyncData<SettingsView>("/api/settings");

  return (
    <div className="space-y-4">
      <PageHeader
        title="Connection"
        description="Review the systems that provide market data, paper execution and backend services."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={health.meta?.demo} backendError={health.meta?.backend_error} />

      {health.status === "loading" && <LoadingState />}
      {health.status === "error" && (
        <ErrorState title="Unable to load connection status" message={health.error} onRetry={health.reload} />
      )}

      {health.status === "success" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="Backend">
            <Row
              label="Status"
              value={
                <Badge tone={health.data.backend_reachable ? "positive" : "negative"}>
                  {health.data.backend_reachable ? "Available" : "Unavailable"}
                </Badge>
              }
            />
            <Row label="API availability" value={health.data.backend_reachable ? "Reachable" : "Unreachable"} />
            <Row label="Trading mode" value={health.data.trading_mode} />
            <Row
              label="Authentication"
              value="Session cookie via Atlas login (server-side)"
            />
          </SectionCard>

          <SectionCard title="Market data">
            <Row label="Provider" value={settings.status === "success" ? settings.data.exchange_id : "Not available"} />
            <Row label="State" value={<Badge tone="warning">Paper / offline fixtures</Badge>} />
            <Row
              label="Freshness threshold"
              value={
                settings.status === "success"
                  ? `${settings.data.market_data_stale_seconds}s`
                  : "Not available"
              }
            />
            <Row label="Live stream" value="Not available" />
          </SectionCard>

          <SectionCard title="Paper broker">
            <Row label="Status" value={<Badge tone="positive">Connected (simulated)</Badge>} />
            <Row
              label="Starting simulated balance"
              value={
                settings.status === "success" ? (
                  <MoneyValue value={10000} size="sm" />
                ) : (
                  "Not available"
                )
              }
            />
            <Row label="Fee / slippage assumptions" value="Configured in backend paper engine" />
            <Row
              label="Supported symbols"
              value={
                settings.status === "success"
                  ? settings.data.supported_symbols.join(", ")
                  : "Not available"
              }
            />
          </SectionCard>

          <SectionCard title="Live exchange">
            <div className="space-y-3">
              <Badge tone="neutral">Not configured</Badge>
              <p className="text-[14px] text-foreground">Live trading is disabled.</p>
              <p className="text-[13px] text-secondary">
                No exchange API or personal wallet is currently connected.
              </p>
            </div>
          </SectionCard>
        </div>
      )}

      <SectionCard title="Security">
        <p className="text-[14px] leading-relaxed text-secondary">
          Project Atlas will never ask for your wallet recovery phrase or private key. Future exchange
          API credentials must use trading-only permissions with withdrawals disabled.
        </p>
      </SectionCard>

      <SectionCard title="Future readiness checklist" description="Based on current repository posture">
        <ul className="space-y-2 text-[14px] text-secondary">
          <li>☐ Live trading remains hard-blocked</li>
          <li>☐ No wallet connect flows</li>
          <li>☐ No seed phrase or private key collection</li>
          <li>☑ Paper broker path available</li>
          <li>☑ Kill switch and risk engine present</li>
          <li>☐ Exchange API credential vault (not implemented)</li>
        </ul>
      </SectionCard>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border/70 py-2.5 text-[14px] last:border-0">
      <span className="text-secondary">{label}</span>
      <span className="text-right text-foreground">{value}</span>
    </div>
  );
}
