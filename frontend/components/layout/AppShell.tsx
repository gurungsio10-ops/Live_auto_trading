"use client";

import { ReactNode, useCallback, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { DesktopSidebar } from "./DesktopSidebar";
import { MobileHeader } from "./MobileHeader";
import { MobileBottomNav } from "./MobileBottomNav";
import { MobileDrawer } from "./MobileDrawer";
import { GlobalStatusStrip } from "./GlobalStatusStrip";
import { useAsyncData } from "@/lib/use-async-data";
import type { HealthStatus, PortfolioSummary } from "@/lib/types";
import { engineFromPortfolio, systemFromHealth } from "@/lib/status";
import { formatRelativeTime } from "@/lib/format";

const BARE = ["/login"];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
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
    portfolio.status === "success" ? Boolean(portfolio.data.kill_switch_enabled) : false;

  const backendOk =
    health.status === "success"
      ? Boolean(health.data.backend_reachable)
      : health.status === "error"
        ? false
        : null;

  const onLogout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      /* ignore */
    }
    router.push("/login");
    router.refresh();
  }, [router]);

  if (BARE.includes(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-dvh min-h-screen overflow-x-hidden">
      <DesktopSidebar
        systemLabel={system === "online" ? "Online" : system === "degraded" ? "Degraded" : "Offline"}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader
          backendOk={backendOk}
          killSwitchOn={killSwitch}
          onMenu={() => setDrawerOpen(true)}
        />
        <main className="mx-auto w-full max-w-content flex-1 px-4 pb-[calc(4.5rem+env(safe-area-inset-bottom))] pt-4 md:px-6 md:pb-8 md:pt-6 lg:px-8">
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
      <MobileBottomNav />
      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onLogout={onLogout} />
    </div>
  );
}
