import { NextRequest, NextResponse } from "next/server";
import { backendFetch, envelope } from "@/lib/backend";
import { demoState } from "@/lib/mock-data";
import type { BacktestReport, BacktestRequest } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await backendFetch<BacktestReport[]>("/backtests");
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    return NextResponse.json(
      envelope(
        demoState.backtests,
        true,
        err instanceof Error ? err.message : "backend down",
      ),
    );
  }
}

export async function POST(req: NextRequest) {
  const body = (await req.json()) as BacktestRequest;

  try {
    const data = await backendFetch<BacktestReport>("/backtests", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return NextResponse.json(envelope(data, false));
  } catch (err) {
    const runId = `bt_demo_${Date.now().toString(36)}`;
    const report: BacktestReport = {
      run_id: runId,
      strategy_id: body.strategy_id,
      status: "completed",
      created_at: new Date().toISOString(),
      config: { ...body },
      metrics: {
        trade_count: 24,
        total_return: "0.0820",
        net_return: "820.00",
        win_rate: "0.5000",
        profit_factor: "1.35",
        max_drawdown: "0.0710",
        sharpe: "0.98",
        sortino: "1.21",
        fees_paid: "54.00",
        slippage_cost: "18.00",
      },
      json_report: {
        run_id: runId,
        strategy_id: body.strategy_id,
        config: body,
        metrics: {
          trade_count: 24,
          total_return: "0.0820",
          max_drawdown: "0.0710",
        },
      },
      markdown_report: [
        `# Backtest Report — ${body.strategy_id}`,
        "",
        `- Run ID: \`${runId}\``,
        `- Symbol: **${body.symbol}**`,
        `- Timeframe: **${body.timeframe}**`,
        `- Window: **${body.start} → ${body.end}**`,
        "- Trades: **24**",
        "- Total return: **0.0820**",
        "- Max drawdown: **0.0710**",
        "- Sharpe: **0.98**",
        "",
        "_Demo report generated because FastAPI backtest endpoint was unavailable._",
        "",
      ].join("\n"),
      error: null,
    };
    demoState.backtests = [report, ...demoState.backtests];
    return NextResponse.json(
      envelope(report, true, err instanceof Error ? err.message : "backend down"),
    );
  }
}
