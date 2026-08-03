import { NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
import type { HealthStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<{
      status: string;
      trading_mode: HealthStatus["trading_mode"];
      live_trading_enabled: boolean;
      kill_switch_enabled: boolean;
      exchange_env: HealthStatus["exchange_env"];
    }>("/health");
    return NextResponse.json(
      envelope(
        {
          ...data,
          backend_reachable: true,
          demo_mode: false,
        } satisfies HealthStatus,
        false,
      ),
    );
  } catch (err) {
    return NextResponse.json(
      envelope(
        {
          status: "demo",
          trading_mode: demoState.portfolio.trading_mode,
          live_trading_enabled: false,
          kill_switch_enabled: demoState.portfolio.kill_switch_enabled,
          exchange_env: demoState.portfolio.exchange_env,
          backend_reachable: false,
          demo_mode: true,
        } satisfies HealthStatus,
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}
