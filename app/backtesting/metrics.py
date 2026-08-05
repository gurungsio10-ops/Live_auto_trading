"""Backtest performance metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.backtesting.engine import BacktestTrade


@dataclass
class PerformanceMetrics:
    total_return: Decimal
    net_return: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    expectancy: Decimal
    max_drawdown: Decimal
    sharpe: Decimal
    sortino: Decimal
    avg_win: Decimal
    avg_loss: Decimal
    risk_reward_ratio: Decimal
    trade_count: int
    exposure_time: Decimal
    consecutive_wins: int
    consecutive_losses: int
    fees_paid: Decimal
    slippage_cost: Decimal
    cagr: Decimal = Decimal("0")
    average_trade: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in raw.items()}


def compute_metrics(
    *,
    trades: list[BacktestTrade],
    equity_curve: list[tuple[datetime, Decimal]],
    initial_cash: Decimal,
    final_equity: Decimal,
) -> PerformanceMetrics:
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    trade_count = len(trades)
    gross_profit = sum(wins, Decimal("0"))
    gross_loss = abs(sum(losses, Decimal("0")))
    net = final_equity - initial_cash
    total_return = (final_equity / initial_cash - 1) if initial_cash else Decimal("0")
    win_rate = (
        (Decimal(len(wins)) / Decimal(trade_count)) if trade_count else Decimal("0")
    )
    profit_factor = (
        (gross_profit / gross_loss)
        if gross_loss > 0
        else (Decimal("Infinity") if gross_profit > 0 else Decimal("0"))
    )
    expectancy = (
        (sum(pnls, Decimal("0")) / Decimal(trade_count))
        if trade_count
        else Decimal("0")
    )
    avg_win = (sum(wins, Decimal("0")) / Decimal(len(wins))) if wins else Decimal("0")
    avg_loss = (
        (sum(losses, Decimal("0")) / Decimal(len(losses))) if losses else Decimal("0")
    )
    rr = (avg_win / abs(avg_loss)) if avg_loss != 0 else Decimal("0")
    fees = sum((t.fees for t in trades), Decimal("0"))
    slip = sum((t.slippage_cost for t in trades), Decimal("0"))

    max_dd = Decimal("0")
    peak = initial_cash
    for _, equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)

    returns = _bar_returns(equity_curve)
    sharpe = _sharpe(returns)
    sortino = _sortino(returns)

    cons_w = _max_streak(pnls, winning=True)
    cons_l = _max_streak(pnls, winning=False)
    average_trade = expectancy

    # Approximate exposure as fraction of bars with open trade intervals
    exposure = Decimal("0")
    if equity_curve and trades:
        total_bars = len(equity_curve)
        in_trade = 0
        times = [t for t, _ in equity_curve]
        for t in trades:
            if t.exit_time is None:
                continue
            in_trade += sum(1 for ts in times if t.entry_time <= ts <= t.exit_time)
        exposure = (
            Decimal(in_trade) / Decimal(total_bars) if total_bars else Decimal("0")
        )

    cagr_value = _cagr(equity_curve, initial_cash, final_equity)

    return PerformanceMetrics(
        total_return=total_return,
        net_return=net,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        win_rate=win_rate,
        profit_factor=(
            profit_factor if profit_factor != Decimal("Infinity") else Decimal("999999")
        ),
        expectancy=expectancy,
        max_drawdown=max_dd,
        sharpe=sharpe,
        sortino=sortino,
        avg_win=avg_win,
        avg_loss=avg_loss,
        risk_reward_ratio=rr,
        trade_count=trade_count,
        exposure_time=exposure,
        consecutive_wins=cons_w,
        consecutive_losses=cons_l,
        fees_paid=fees,
        slippage_cost=slip,
        cagr=cagr_value,
        average_trade=average_trade,
    )


def _cagr(
    equity_curve: list[tuple[datetime, Decimal]],
    initial_cash: Decimal,
    final_equity: Decimal,
) -> Decimal:
    if len(equity_curve) < 2 or initial_cash <= 0 or final_equity <= 0:
        return Decimal("0")
    start_t = equity_curve[0][0]
    end_t = equity_curve[-1][0]
    days = max((end_t - start_t).total_seconds() / 86400.0, 1.0)
    years = days / 365.25
    if years <= 0:
        return Decimal("0")
    ratio = float(final_equity / initial_cash)
    try:
        cagr = ratio ** (1.0 / years) - 1.0
    except Exception:
        return Decimal("0")
    return Decimal(str(cagr)).quantize(Decimal("0.0001"))


def _bar_returns(equity_curve: list[tuple[datetime, Decimal]]) -> list[Decimal]:
    if len(equity_curve) < 2:
        return []
    out: list[Decimal] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1][1]
        cur = equity_curve[i][1]
        if prev > 0:
            out.append((cur - prev) / prev)
    return out


def _sharpe(returns: list[Decimal]) -> Decimal:
    if len(returns) < 2:
        return Decimal("0")
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    var = sum((r - mean) ** 2 for r in returns) / Decimal(len(returns) - 1)
    std = var.sqrt()
    if std == 0:
        return Decimal("0")
    return mean / std


def _sortino(returns: list[Decimal]) -> Decimal:
    if len(returns) < 2:
        return Decimal("0")
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    downside = [r for r in returns if r < 0]
    if not downside:
        return Decimal("0")
    var = sum((r) ** 2 for r in downside) / Decimal(len(downside))
    std = var.sqrt()
    if std == 0:
        return Decimal("0")
    return mean / std


def _max_streak(pnls: list[Decimal], *, winning: bool) -> int:
    best = cur = 0
    for p in pnls:
        ok = p > 0 if winning else p < 0
        if ok:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best
