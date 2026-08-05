"use client";

import { ReactNode, useCallback, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { DesktopSidebar } from "./DesktopSidebar";
import { MobileHeader } from "./MobileHeader";
import { MobileBottomNav } from "./MobileBottomNav";
import { MobileDrawer } from "./MobileDrawer";
import { GlobalStatusStrip } from "./GlobalStatusStrip";
import { useAsyncData } from "@/lib/use-async-data";
import type { PortfolioSummary } from "@/lib/types";
import {
  mapEngineState,
  mapSystemState,
  type UnifiedStatus,
} from "@/lib/status";
import { formatRelativeTime } from "@/lib/format";

const BARE = ["/login"];

function schedulerLabel(status?: UnifiedStatus["scheduler"]): string {
  if (!status) return "—";
  const state = (status.state || "").toUpperCase();
  if (state === "RUNNING") return "Running";
  if (state === "PAUSED") return "Paused";
  if (state === "IDLE") return "Idle";
  if (state === "OFF") return "Off";
  if (state === "DISCONNECTED") return "Unavailable";
  if (status.worker_running) return "Running";
  if (status.enabled && status.paused) return "Paused";
  if (status.enabled) return "Idle";
  return "Off";
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const unified = useAsyncData<UnifiedStatus>("/api/system-status");
  const portfolio = useAsyncData<PortfolioSummary>("/api/portfolio");

  const unifiedData = unified.status === "success" ? unified.data : null;
  const degradedReasons = useMemo(() => {
    if (!unifiedData) {
      if (unified.status === "error") return [unified.error || "Backend unreachable"];
      return [];
    }
    return (
      unifiedData.degraded_reasons ||
      unifiedData.system?.degraded_reasons ||
      unifiedData.engine?.reasons ||
      []
    );
  }, [unified, unifiedData]);

  const system = mapSystemState(unifiedData?.status || unifiedData?.system?.state, degradedReasons);
  const engine = mapEngineState(unifiedData?.engine?.state);
  const killSwitch =
    unifiedData?.kill_switch?.enabled ??
    (portfolio.status === "success" ? Boolean(portfolio.data.kill_switch_enabled) : false);

  const backendOk =
    unified.status === "success"
      ? !["DISCONNECTED", "ERROR"].includes(String(unifiedData?.status || "").toUpperCase())
      : unified.status === "error"
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
        systemLabel={
          system === "online" || system === "ok" || system === "running"
            ? "Online"
            : system === "degraded" || system === "paused"
              ? "Degraded"
              : "Offline"
        }
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader
          backendOk={backendOk}
          killSwitchOn={Boolean(killSwitch)}
          onMenu={() => setDrawerOpen(true)}
        />
        <main className="mx-auto w-full max-w-content flex-1 px-4 pb-[calc(4.5rem+env(safe-area-inset-bottom))] pt-4 md:px-6 md:pb-8 md:pt-6 lg:px-8">
          <GlobalStatusStrip
            engine={engine}
            system={system}
            killSwitch={Boolean(killSwitch)}
            schedulerLabel={schedulerLabel(unifiedData?.scheduler)}
            degradedReasons={degradedReasons}
            lastUpdate={
              unifiedData?.timestamp
                ? formatRelativeTime(unifiedData.timestamp)
                : unified.status === "success"
                  ? formatRelativeTime(new Date().toISOString())
                  : "—"
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
