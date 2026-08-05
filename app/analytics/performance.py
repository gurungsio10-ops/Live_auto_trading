"""Performance engine — metrics over closed paper trades + live portfolio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.analytics.trade_journal import ClosedTrade
from app.core.time import ensure_utc, utc_now


def _q(value: Decimal, places: str = "0.01") -> Decimal:
    return Decimal(value).quantize(Decimal(places))


def _d(value: Decimal, places: str = "0.01") -> str:
    return str(_q(value, places))


@dataclass
class PerformanceSnapshot:
    current_balance: Decimal
    starting_balance: Decimal
    unrealised_pnl: Decimal
    realised_pnl: Decimal
    daily_pnl: Decimal
    weekly_pnl: Decimal
    monthly_pnl: Decimal
    roi_pct: Decimal
    win_rate: Decimal
    loss_rate: Decimal
    profit_factor: Decimal
    average_win: Decimal
    average_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    maximum_drawdown: Decimal
    consecutive_wins: int
    consecutive_losses: int
    average_holding_time: Decimal
    total_fees: Decimal
    total_simulated_volume: Decimal
    trade_count: int
    open_position_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_balance": _d(self.current_balance),
            "starting_balance": _d(self.starting_balance),
            "unrealised_pnl": _d(self.unrealised_pnl),
            "unrealized_pnl": _d(self.unrealised_pnl),
            "realised_pnl": _d(self.realised_pnl),
            "realized_pnl": _d(self.realised_pnl),
            "daily_pnl": _d(self.daily_pnl),
            "weekly_pnl": _d(self.weekly_pnl),
            "monthly_pnl": _d(self.monthly_pnl),
            "roi_pct": str(self.roi_pct.quantize(Decimal("0.0001"))),
            "win_rate": str(self.win_rate.quantize(Decimal("0.0001"))),
            "loss_rate": str(self.loss_rate.quantize(Decimal("0.0001"))),
            "profit_factor": str(self.profit_factor.quantize(Decimal("0.0001"))),
            "average_win": _d(self.average_win),
            "average_loss": _d(self.average_loss),
            "largest_win": _d(self.largest_win),
            "largest_loss": _d(self.largest_loss),
            "maximum_drawdown": str(self.maximum_drawdown.quantize(Decimal("0.0001"))),
            "max_drawdown": str(self.maximum_drawdown.quantize(Decimal("0.0001"))),
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "average_holding_time": str(
                self.average_holding_time.quantize(Decimal("0.01"))
            ),
            "total_fees": _d(self.total_fees, "0.00000001"),
            "total_simulated_volume": _d(self.total_simulated_volume),
            "trade_count": self.trade_count,
            "open_position_count": self.open_position_count,
            "banner": "PAPER TRADING — NO REAL FUNDS",
        }


class PerformanceEngine:
    """Compute evaluation metrics from closed trades + current paper state."""

    def __init__(self, *, starting_balance: Decimal = Decimal("10000")) -> None:
        self.starting_balance = Decimal(starting_balance)

    def compute(
        self,
        *,
        trades: list[ClosedTrade],
        current_balance: Decimal,
        unrealised_pnl: Decimal,
        realised_pnl: Decimal | None = None,
        equity_curve: list[dict[str, Any]] | None = None,
        open_position_count: int = 0,
        now: datetime | None = None,
    ) -> PerformanceSnapshot:
        now = ensure_utc(now or utc_now())
        pnls = [t.net_pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        count = len(trades)
        win_rate = Decimal(len(wins)) / Decimal(count) if count else Decimal("0")
        loss_rate = Decimal(len(losses)) / Decimal(count) if count else Decimal("0")
        gross_profit = sum(wins, Decimal("0"))
        gross_loss = abs(sum(losses, Decimal("0")))
        profit_factor = (
            (gross_profit / gross_loss)
            if gross_loss > 0
            else (Decimal("999999") if gross_profit > 0 else Decimal("0"))
        )
        avg_win = sum(wins, Decimal("0")) / Decimal(len(wins)) if wins else Decimal("0")
        avg_loss = (
            sum(losses, Decimal("0")) / Decimal(len(losses)) if losses else Decimal("0")
        )
        largest_win = max(wins) if wins else Decimal("0")
        largest_loss = min(losses) if losses else Decimal("0")
        fees = sum((t.fees for t in trades), Decimal("0"))
        volume = sum((t.entry_price * t.quantity for t in trades), Decimal("0")) + sum(
            (t.exit_price * t.quantity for t in trades), Decimal("0")
        )
        avg_hold = (
            Decimal(sum(t.duration_seconds for t in trades)) / Decimal(count)
            if count
            else Decimal("0")
        )
        cons_w = _max_streak(pnls, winning=True)
        cons_l = _max_streak(pnls, winning=False)
        max_dd = _max_drawdown(equity_curve, self.starting_balance, current_balance)
        roi = (
            ((current_balance / self.starting_balance) - 1) * Decimal("100")
            if self.starting_balance > 0
            else Decimal("0")
        )
        realized = realised_pnl if realised_pnl is not None else sum(pnls, Decimal("0"))
        daily = _period_pnl(trades, equity_curve, current_balance, now, days=1)
        weekly = _period_pnl(trades, equity_curve, current_balance, now, days=7)
        monthly = _period_pnl(trades, equity_curve, current_balance, now, days=30)

        return PerformanceSnapshot(
            current_balance=Decimal(current_balance),
            starting_balance=self.starting_balance,
            unrealised_pnl=Decimal(unrealised_pnl),
            realised_pnl=Decimal(realized),
            daily_pnl=daily,
            weekly_pnl=weekly,
            monthly_pnl=monthly,
            roi_pct=roi,
            win_rate=win_rate,
            loss_rate=loss_rate,
            profit_factor=profit_factor,
            average_win=avg_win,
            average_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            maximum_drawdown=max_dd,
            consecutive_wins=cons_w,
            consecutive_losses=cons_l,
            average_holding_time=avg_hold,
            total_fees=fees,
            total_simulated_volume=volume,
            trade_count=count,
            open_position_count=open_position_count,
        )

    def strategy_rankings(
        self, trades: list[ClosedTrade], *, starting_balance: Decimal | None = None
    ) -> list[dict[str, Any]]:
        start = starting_balance or self.starting_balance
        by_strategy: dict[str, list[ClosedTrade]] = {}
        for t in trades:
            by_strategy.setdefault(t.strategy_name, []).append(t)
        rankings: list[dict[str, Any]] = []
        for name, group in by_strategy.items():
            net = sum((t.net_pnl for t in group), Decimal("0"))
            wins = sum(1 for t in group if t.net_pnl > 0)
            count = len(group)
            volume = sum((t.entry_price * t.quantity for t in group), Decimal("0"))
            alloc = (volume / start) if start > 0 else Decimal("0")
            rankings.append(
                {
                    "strategy_name": name,
                    "trade_count": count,
                    "net_pnl": _d(net),
                    "win_rate": str(
                        (Decimal(wins) / Decimal(count)).quantize(Decimal("0.0001"))
                        if count
                        else "0"
                    ),
                    "total_fees": _d(
                        sum((t.fees for t in group), Decimal("0")), "0.00000001"
                    ),
                    "capital_allocation_proxy": str(alloc.quantize(Decimal("0.0001"))),
                    "avg_roi_pct": str(
                        (
                            sum((t.roi_pct for t in group), Decimal("0"))
                            / Decimal(count)
                        ).quantize(Decimal("0.0001"))
                        if count
                        else "0"
                    ),
                }
            )
        rankings.sort(key=lambda r: Decimal(r["net_pnl"]), reverse=True)
        for i, row in enumerate(rankings, start=1):
            row["rank"] = i
        return rankings

    def monthly_performance(self, trades: list[ClosedTrade]) -> list[dict[str, Any]]:
        buckets: dict[str, list[ClosedTrade]] = {}
        for t in trades:
            key = ensure_utc(t.exit_time).strftime("%Y-%m")
            buckets.setdefault(key, []).append(t)
        rows: list[dict[str, Any]] = []
        for month in sorted(buckets.keys()):
            group = buckets[month]
            net = sum((t.net_pnl for t in group), Decimal("0"))
            wins = sum(1 for t in group if t.net_pnl > 0)
            rows.append(
                {
                    "month": month,
                    "trade_count": len(group),
                    "net_pnl": _d(net),
                    "win_rate": str(
                        (Decimal(wins) / Decimal(len(group))).quantize(
                            Decimal("0.0001")
                        )
                        if group
                        else "0"
                    ),
                }
            )
        return rows


def build_equity_series(
    equity_points: list[dict[str, Any]],
    *,
    starting_balance: Decimal,
) -> dict[str, list[dict[str, Any]]]:
    """Balance / drawdown / daily-return histories for charts."""
    balance_history: list[dict[str, Any]] = []
    drawdown_history: list[dict[str, Any]] = []
    daily_returns: list[dict[str, Any]] = []
    peak = starting_balance
    day_close: dict[str, Decimal] = {}

    for point in equity_points:
        ts = str(point.get("time") or point.get("created_at") or "")
        equity = Decimal(str(point.get("equity", "0")))
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else Decimal("0")
        if point.get("drawdown") is not None:
            try:
                dd = Decimal(str(point["drawdown"]))
            except Exception:
                pass
        balance_history.append(
            {"time": ts, "equity": _d(equity), "balance": _d(equity)}
        )
        drawdown_history.append(
            {"time": ts, "drawdown": str(dd.quantize(Decimal("0.0001")))}
        )
        day = ts[:10]
        if day:
            day_close[day] = equity

    days = sorted(day_close.keys())
    prev_eq = starting_balance
    for day in days:
        eq = day_close[day]
        ret = (eq - prev_eq) / prev_eq if prev_eq > 0 else Decimal("0")
        daily_returns.append(
            {
                "date": day,
                "return_pct": str((ret * Decimal("100")).quantize(Decimal("0.0001"))),
            }
        )
        prev_eq = eq

    return {
        "balance_history": balance_history,
        "drawdown_history": drawdown_history,
        "daily_return_history": daily_returns,
    }


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


def _max_drawdown(
    equity_curve: list[dict[str, Any]] | None,
    starting: Decimal,
    current: Decimal,
) -> Decimal:
    peak = starting
    max_dd = Decimal("0")
    if equity_curve:
        for point in equity_curve:
            eq = Decimal(str(point.get("equity", "0")))
            peak = max(peak, eq)
            if peak > 0:
                max_dd = max(max_dd, (peak - eq) / peak)
    peak = max(peak, current)
    if peak > 0:
        max_dd = max(max_dd, (peak - current) / peak)
    return max_dd


def _period_pnl(
    trades: list[ClosedTrade],
    equity_curve: list[dict[str, Any]] | None,
    current: Decimal,
    now: datetime,
    *,
    days: int,
) -> Decimal:
    cutoff = now - timedelta(days=days)
    # Prefer equity curve window when enough points.
    if equity_curve:
        in_window: list[tuple[datetime, Decimal]] = []
        for p in equity_curve:
            ts_raw = str(p.get("time") or p.get("created_at") or "")
            if not ts_raw:
                continue
            try:
                ts = ensure_utc(datetime.fromisoformat(ts_raw.replace("Z", "+00:00")))
            except ValueError:
                continue
            if ts >= cutoff:
                in_window.append((ts, Decimal(str(p["equity"]))))
        if len(in_window) >= 2:
            in_window.sort(key=lambda x: x[0])
            return in_window[-1][1] - in_window[0][1]
    period_trades = [t for t in trades if ensure_utc(t.exit_time) >= cutoff]
    if period_trades:
        return sum((t.net_pnl for t in period_trades), Decimal("0"))
    return Decimal("0")
