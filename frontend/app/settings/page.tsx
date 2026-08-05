"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { Badge, PaperTradingBadge } from "@/components/ui/Badge";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingSkeleton";
import { DeveloperProfile } from "@/components/brand/DeveloperProfile";
import { LockedSettingRow } from "@/components/ui/LockedSettingRow";
import { useAsyncData } from "@/lib/use-async-data";
import { formatMoney, formatPct } from "@/lib/format";
import { BRAND } from "@/lib/brand";
import type { SettingsView } from "@/lib/types";

export default function SettingsPage() {
  const { status, data, error, meta, reload } = useAsyncData<SettingsView>("/api/settings");
  const [theme, setTheme] = useState("dark");
  const [currency, setCurrency] = useState("USD");

  useEffect(() => {
    try {
      setTheme(localStorage.getItem("atlas.theme") ?? "dark");
      setCurrency(localStorage.getItem("atlas.currency") ?? "USD");
    } catch {
      /* ignore */
    }
  }, []);

  function persist(key: string, value: string) {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Settings"
        description="Manage appearance, display preferences and available paper-trading options."
        meta={<PaperTradingBadge />}
      />
      <DemoBanner demo={meta?.demo} backendError={meta?.backend_error} />

      <SectionCard title="Appearance">
        <label className="block text-[13px] text-secondary">
          Theme
          <select
            className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface-raised px-3 text-foreground"
            value={theme}
            onChange={(e) => {
              setTheme(e.target.value);
              persist("atlas.theme", e.target.value);
            }}
          >
            <option value="dark">Dark</option>
            <option value="light" disabled>
              Light (not available yet)
            </option>
            <option value="system" disabled>
              System (not available yet)
            </option>
          </select>
        </label>
      </SectionCard>

      <SectionCard title="Display">
        <label className="block text-[13px] text-secondary">
          Currency display format
          <select
            className="mt-2 min-h-touch w-full rounded-control border border-border bg-surface-raised px-3 text-foreground"
            value={currency}
            onChange={(e) => {
              setCurrency(e.target.value);
              persist("atlas.currency", e.target.value);
            }}
          >
            <option value="USD">USD ($)</option>
            <option value="GBP">GBP (£) display only — no FX conversion</option>
          </select>
        </label>
        <p className="mt-2 text-[12px] text-muted">
          Backend paper balances are simulated in USD/USDT terms. GBP is a display preference only.
        </p>
      </SectionCard>

      {status === "loading" && <LoadingState />}
      {status === "error" && <ErrorState message={error} onRetry={reload} />}
      {status === "success" && (
        <>
          <SectionCard title="Paper trading" description="Read-only unless secure update endpoints exist">
            <LockedSettingRow label="Trading mode" value={data.trading_mode.toUpperCase()} />
            <LockedSettingRow
              label="Live trading enabled"
              value={data.live_trading_enabled ? "true" : "false"}
            />
            <LockedSettingRow label="Exchange env" value={data.exchange_env} />
            <LockedSettingRow label="Exchange id" value={data.exchange_id} />
            <LockedSettingRow
              label="Market data stale (s)"
              value={String(data.market_data_stale_seconds)}
            />
          </SectionCard>

          <SectionCard title="Risk" description="Active rules (read-only)">
            <LockedSettingRow
              label="Max risk / trade"
              value={formatPct(data.risk_limits.max_risk_per_trade)}
            />
            <LockedSettingRow
              label="Max position exposure"
              value={formatPct(data.risk_limits.max_position_exposure)}
            />
            <LockedSettingRow
              label="Max portfolio exposure"
              value={formatPct(data.risk_limits.max_portfolio_exposure)}
            />
            <LockedSettingRow
              label="Max daily loss"
              value={formatPct(data.risk_limits.max_daily_loss)}
            />
            <LockedSettingRow
              label="Max drawdown"
              value={formatPct(data.risk_limits.max_drawdown)}
            />
            <LockedSettingRow
              label="Min order notional"
              value={formatMoney(data.risk_limits.min_order_notional)}
            />
          </SectionCard>

          <SectionCard title="Security">
            <LockedSettingRow label="Authentication" value="Signed HTTP-only session cookie" />
            <LockedSettingRow label="Secrets in browser storage" value="None" />
            <p className="mt-3 text-[13px] text-secondary">
              API tokens and auth secrets remain server-side. Atlas never requests seed phrases or
              private keys.
            </p>
          </SectionCard>
        </>
      )}

      <SectionCard title="About" description="Product identity">
        <div id="about" className="scroll-mt-24 space-y-4">
          <div>
            <p className="text-xl font-bold text-foreground">{BRAND.name}</p>
            <p className="mt-1 text-[14px] text-secondary">{BRAND.subtitle}</p>
            <div className="mt-3">
              <PaperTradingBadge />
            </div>
          </div>
          <DeveloperProfile />
          <div className="grid gap-2 text-[13px] text-secondary sm:grid-cols-2">
            <p>Version · {BRAND.version}</p>
            <p>Environment · {process.env.NODE_ENV}</p>
            <p>Current mode · Paper trading</p>
            <p>Purpose · Personal research, testing and strategy evaluation</p>
          </div>
          <p className="text-[12px] text-muted">
            Optional owner photo path: {BRAND.ownerImageFsPath}
          </p>
        </div>
      </SectionCard>
    </div>
  );
}
