"use client";

import { ReactNode, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { DesktopSidebar } from "./DesktopSidebar";
import { MobileHeader } from "./MobileHeader";
import { MobileBottomNav } from "./MobileBottomNav";
import { MobileMoreSheet } from "./MobileMoreSheet";
import { GlobalStatusStrip } from "./GlobalStatusStrip";
import { useAsyncData } from "@/lib/use-async-data";
import type { HealthStatus, PortfolioSummary } from "@/lib/types";
import { engineFromPortfolio, systemFromHealth } from "@/lib/status";
import { formatRelativeTime } from "@/lib/format";
import { NAV_ITEMS } from "@/lib/nav";

const BARE = ["/login"];

function titleForPath(pathname: string): string {
  const hit = NAV_ITEMS.find((n) => {
    if (n.href === "/") return pathname === "/";
    return pathname === n.href || pathname.startsWith(`${n.href}/`);
  });
  return hit?.label ?? "Atlas";
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const health = useAsyncData<HealthStatus>("/api/health");
  const portfolio = useAsyncData<PortfolioSummary>("/api/portfolio");
  const strategies = useAsyncData<{ running?: boolean; selected?: boolean }[]>(
    "/api/strategies",
  );

  const system = useMemo(() => {
    if (health.status !== "success") return systemFromHealth({});
    return systemFromHealth({
      backend_reachable: health.data.backend_reachable,
      demo: health.meta?.demo,
      backend_error: health.meta?.backend_error,
    });
  }, [health]);

  const engine = useMemo(() => {
    const strategyRunning =
      strategies.status === "success"
        ? strategies.data.some((s) => s.running || s.selected)
        : null;
    if (portfolio.status !== "success") {
      return engineFromPortfolio({ strategyRunning });
    }
    return engineFromPortfolio({
      trading_paused: portfolio.data.trading_paused,
      kill_switch_enabled: portfolio.data.kill_switch_enabled,
      strategyRunning,
    });
  }, [portfolio, strategies]);

  const killSwitch =
    portfolio.status === "success" ? portfolio.data.kill_switch_enabled : false;

  if (BARE.includes(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-dvh min-h-screen overflow-x-hidden">
      <DesktopSidebar
        systemLabel={system === "online" ? "Online" : system === "degraded" ? "Degraded" : "Offline"}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader title={titleForPath(pathname)} systemOnline={system === "online"} />
        <main className="mx-auto w-full max-w-content flex-1 px-4 pb-safe pt-4 md:px-6 md:pt-6 lg:px-8 lg:pb-8 safe-pb lg:pb-8">
          <div className="hidden lg:block">
            {/* desktop page content starts below strip inside pages via composition; strip always shown */}
          </div>
          <GlobalStatusStrip
            engine={engine}
            system={system}
            killSwitch={killSwitch}
            lastUpdate={
              health.status === "success" ? formatRelativeTime(new Date().toISOString()) : "—"
            }
          />
          {children}
        </main>
      </div>
      <MobileBottomNav onMore={() => setMoreOpen(true)} />
      <MobileMoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} />
    </div>
  );
}
