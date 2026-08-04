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
import { formatPct, formatTs } from "@/lib/format";

export function DrawdownChart({ data }: { data: EquityPoint[] }) {
  const chartData = data.map((p) => ({
    time: p.time,
    drawdown: Number(p.drawdown) * (Number(p.drawdown) <= 1 ? 100 : 1),
    label: formatTs(p.time).slice(5, 16),
  }));
  const maxDd = chartData.reduce((m, p) => Math.max(m, p.drawdown || 0), 0);

  return (
    <div className="w-full min-w-0">
      <p className="sr-only">
        Paper drawdown chart. Peak drawdown in view: {formatPct(maxDd)}.
      </p>
      <div className="h-48 w-full min-w-0 sm:h-56">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ff6b6b" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#ff6b6b" stopOpacity={0} />
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
              width={44}
              tickFormatter={(v) => `${Number(v).toFixed(0)}%`}
              domain={[0, "auto"]}
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
              formatter={(value: number) => [formatPct(value), "Paper drawdown"]}
            />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="#ff6b6b"
              strokeWidth={2}
              fill="url(#ddFill)"
              isAnimationActive
              animationDuration={500}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
