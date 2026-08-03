"""Backtest report writers (JSON + Markdown)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.backtesting.engine import BacktestResult


def write_json_report(result: BacktestResult, directory: Path) -> Path:
    path = directory / f"backtest_{result.run_id}.json"
    payload = {
        "run_id": result.run_id,
        "strategy_id": result.strategy_id,
        "config": result.config,
        "metrics": result.metrics.to_dict(),
        "trades": [
            {
                "symbol": t.symbol,
                "side": t.side,
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "entry_price": str(t.entry_price),
                "exit_price": str(t.exit_price) if t.exit_price is not None else None,
                "quantity": str(t.quantity),
                "pnl": str(t.pnl),
                "fees": str(t.fees),
                "slippage_cost": str(t.slippage_cost),
                "reason": t.reason,
            }
            for t in result.trades
        ],
        "equity_curve": [
            {"time": t.isoformat(), "equity": str(eq)} for t, eq in result.equity_curve
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_markdown_summary(result: BacktestResult, directory: Path) -> Path:
    path = directory / f"backtest_{result.run_id}.md"
    m = result.metrics
    lines = [
        f"# Backtest Report — {result.strategy_id}",
        "",
        f"- Run ID: `{result.run_id}`",
        f"- Trades: **{m.trade_count}**",
        f"- Total return: **{m.total_return}**",
        f"- Net P&L: **{m.net_return}**",
        f"- Win rate: **{m.win_rate}**",
        f"- Profit factor: **{m.profit_factor}**",
        f"- Max drawdown: **{m.max_drawdown}**",
        f"- Sharpe: **{m.sharpe}**",
        f"- Sortino: **{m.sortino}**",
        f"- Fees paid: **{m.fees_paid}**",
        f"- Slippage cost: **{m.slippage_cost}**",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
