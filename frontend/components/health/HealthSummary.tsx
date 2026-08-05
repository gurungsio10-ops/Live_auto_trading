"use client";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

export type HealthState = "healthy" | "degraded" | "unavailable" | "unknown";

export type HealthItem = {
  id: string;
  label: string;
  state: HealthState;
  detail?: string;
};

function tone(state: HealthState): "gain" | "warn" | "danger" | "neutral" {
  switch (state) {
    case "healthy":
      return "gain";
    case "degraded":
      return "warn";
    case "unavailable":
      return "danger";
    default:
      return "neutral";
  }
}

function label(state: HealthState): string {
  switch (state) {
    case "healthy":
      return "Healthy";
    case "degraded":
      return "Degraded";
    case "unavailable":
      return "Unavailable";
    default:
      return "Unknown";
  }
}

export function HealthSummary({ items }: { items: HealthItem[] }) {
  const worst = items.reduce<HealthState>((acc, item) => {
    const rank = { healthy: 0, unknown: 1, degraded: 2, unavailable: 3 } as const;
    return rank[item.state] > rank[acc] ? item.state : acc;
  }, "healthy");

  return (
    <Card
      title="System health"
      subtitle="Backend, data plane, scheduler, and risk path"
      actions={<Badge tone={tone(worst)}>{label(worst)}</Badge>}
    >
      <ul className="grid grid-cols-1 gap-2 min-[390px]:grid-cols-2 xl:grid-cols-4">
        {items.map((item) => (
          <li
            key={item.id}
            className="min-w-0 border border-terminal-border bg-terminal-elevated/40 px-3 py-3"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-[11px] uppercase tracking-wide text-terminal-dim">
                {item.label}
              </p>
              <Badge tone={tone(item.state)}>{label(item.state)}</Badge>
            </div>
            {item.detail ? (
              <p className="mt-2 truncate text-[11px] font-mono text-terminal-text" title={item.detail}>
                {item.detail}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function deriveHealthItems(input: {
  backendOk?: boolean | null;
  databaseOk?: boolean | null;
  redisOk?: boolean | null;
  marketDataOk?: boolean | null;
  schedulerEnabled?: boolean | null;
  schedulerRunning?: boolean | null;
  schedulerError?: string | null;
  engineOk?: boolean | null;
  reconciliationOk?: boolean | null;
}): HealthItem[] {
  const boolState = (v: boolean | null | undefined): HealthState => {
    if (v === true) return "healthy";
    if (v === false) return "unavailable";
    return "unknown";
  };

  let schedulerState: HealthState = "unknown";
  let schedulerDetail = "—";
  if (input.schedulerEnabled === false) {
    schedulerState = "degraded";
    schedulerDetail = "Disabled by config";
  } else if (input.schedulerError) {
    schedulerState = "unavailable";
    schedulerDetail = "Error";
  } else if (input.schedulerRunning) {
    schedulerState = "healthy";
    schedulerDetail = "Running";
  } else if (input.schedulerEnabled) {
    schedulerState = "degraded";
    schedulerDetail = "Enabled, not running";
  }

  return [
    {
      id: "backend",
      label: "Backend",
      state: boolState(input.backendOk),
      detail: input.backendOk ? "Reachable" : input.backendOk === false ? "Unreachable" : "—",
    },
    {
      id: "postgres",
      label: "PostgreSQL",
      state: boolState(input.databaseOk),
      detail: input.databaseOk === true ? "OK" : input.databaseOk === false ? "Unhealthy" : "—",
    },
    {
      id: "redis",
      label: "Redis",
      state: boolState(input.redisOk),
      detail: input.redisOk === true ? "OK" : input.redisOk === false ? "Unhealthy" : "Not reported",
    },
    {
      id: "market",
      label: "Market data",
      state: boolState(input.marketDataOk),
      detail:
        input.marketDataOk === true
          ? "Fresh"
          : input.marketDataOk === false
            ? "Stale / unavailable"
            : "Paper fixtures",
    },
    {
      id: "scheduler",
      label: "Scheduler",
      state: schedulerState,
      detail: schedulerDetail,
    },
    {
      id: "engine",
      label: "Trading engine",
      state: boolState(input.engineOk ?? input.backendOk),
      detail: "Paper engine",
    },
    {
      id: "recon",
      label: "Reconciliation",
      state: boolState(input.reconciliationOk),
      detail:
        input.reconciliationOk === true
          ? "Healthy"
          : input.reconciliationOk === false
            ? "Halted / unhealthy"
            : "—",
    },
  ];
}
