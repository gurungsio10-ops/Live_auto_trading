"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint } from "@/lib/types";
import { formatCompactMoney, formatMoney, formatTs } from "@/lib/format";

export function EquityCurveChart({ data }: { data: EquityPoint[] }) {
  const chartData = data.map((p) => ({
    time: p.time,
    equity: Number(p.equity),
    label: formatTs(p.time).slice(5, 16),
  }));
  const first = chartData[0]?.equity;
  const last = chartData[chartData.length - 1]?.equity;
  const summary =
    first != null && last != null
      ? `Paper equity from ${formatMoney(first)} to ${formatMoney(last)} across ${chartData.length} points.`
      : "Paper equity chart unavailable.";

  return (
    <div className="w-full min-w-0">
      <p className="sr-only">{summary}</p>
      <div className="h-56 w-full min-w-0 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3ddeb5" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#3ddeb5" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(36,48,65,0.9)" strokeDasharray="3 3" />
            <XAxis
              dataKey="label"
              tick={{ fill: "#9aabbf", fontSize: 10, fontFamily: "var(--font-mono)" }}
              tickLine={false}
              axisLine={{ stroke: "#243041" }}
              minTickGap={40}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: "#9aabbf", fontSize: 10, fontFamily: "var(--font-mono)" }}
              tickLine={false}
              axisLine={{ stroke: "#243041" }}
              width={52}
              tickFormatter={(v) => formatCompactMoney(v)}
            />
            <Tooltip
              contentStyle={{
                background: "#0d1218",
                border: "1px solid #243041",
                borderRadius: 2,
                fontFamily: "var(--font-mono)",
                fontSize: 11,
              }}
              labelFormatter={(_, payload) =>
                payload?.[0]?.payload?.time ? formatTs(payload[0].payload.time) : ""
              }
              formatter={(value: number) => [formatMoney(value), "Paper equity"]}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke="#3ddeb5"
              strokeWidth={2}
              fill="url(#equityFill)"
              isAnimationActive
              animationDuration={500}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
