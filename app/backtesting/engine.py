"""Event-driven backtesting engine — no look-ahead bias."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.backtesting.metrics import PerformanceMetrics, compute_metrics
from app.backtesting.reports import write_json_report, write_markdown_summary
from app.models.domain.enums import OrderSide, SignalDirection
from app.models.domain.market import Candle
from app.models.domain.trading import PortfolioState, Position
from app.strategies.base import Strategy, StrategyConfig, StrategyContext


@dataclass
class BacktestTrade:
    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime | None
    entry_price: Decimal
    exit_price: Decimal | None
    quantity: Decimal
    pnl: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    slippage_cost: Decimal = Decimal("0")
    reason: str = ""


@dataclass
class BacktestConfig:
    initial_cash: Decimal = Decimal("10000")
    fee_rate: Decimal = Decimal("0.001")
    slippage_rate: Decimal = Decimal("0.0005")
    spread_rate: Decimal = Decimal("0.0002")
    position_size_fraction: Decimal = Decimal("0.1")
    allow_short: bool = False
    one_position_per_symbol: bool = True
    report_dir: Path = Path("app/backtesting/reports")


@dataclass
class BacktestResult:
    metrics: PerformanceMetrics
    trades: list[BacktestTrade]
    equity_curve: list[tuple[datetime, Decimal]]
    config: dict[str, Any]
    strategy_id: str
    json_path: Path | None = None
    markdown_path: Path | None = None
    run_id: str = field(default_factory=lambda: uuid4().hex)


class BacktestEngine:
    """Long-only, one position per symbol, event-driven on closed candles."""

    def __init__(
        self, strategy: Strategy, config: BacktestConfig | None = None
    ) -> None:
        self.strategy = strategy
        self.config = config or BacktestConfig()

    def run(
        self,
        candles: list[Candle],
        *,
        strategy_config: StrategyConfig | None = None,
        write_reports: bool = True,
    ) -> BacktestResult:
        if not candles:
            raise ValueError("candles must not be empty")

        cfg = strategy_config or self.strategy.default_config()
        cash = self.config.initial_cash
        position: Position | None = None
        trades: list[BacktestTrade] = []
        equity_curve: list[tuple[datetime, Decimal]] = []
        open_trade: BacktestTrade | None = None
        bars_held = 0
        peak = cash

        # Process bar i using only candles[: i+1] — no look-ahead.
        for i in range(len(candles)):
            window = candles[: i + 1]
            bar = window[-1]
            mark = bar.close
            unrealized = Decimal("0")
            if position is not None:
                unrealized = (mark - position.entry_price) * position.quantity
                position = position.model_copy(
                    update={"current_price": mark, "unrealized_pnl": unrealized}
                )
                bars_held += 1

            equity = cash + (
                position.quantity * mark if position is not None else Decimal("0")
            )
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak if peak > 0 else Decimal("0")
            portfolio = PortfolioState(
                cash_balance=cash,
                equity=equity,
                unrealized_pnl=unrealized,
                peak_equity=peak,
                drawdown=drawdown,
                open_positions=[position] if position else [],
            )
            equity_curve.append((bar.open_time, equity))

            ctx = StrategyContext(
                candles=window,
                portfolio=portfolio,
                position=position,
                indicators={"bars_held": bars_held},
                config=cfg,
            )
            signal = self.strategy.evaluate(ctx)

            if signal.direction == SignalDirection.BUY and position is None:
                qty = self._size_position(cash, mark)
                if qty > 0:
                    fill = self._apply_costs(mark, side=OrderSide.BUY)
                    cost = fill["price"] * qty
                    fees = fill["fee"] * qty
                    slip = fill["slippage_cost"] * qty
                    if cost + fees <= cash:
                        cash -= cost + fees
                        position = Position(
                            symbol=bar.symbol,
                            quantity=qty,
                            entry_price=fill["price"],
                            current_price=mark,
                            unrealized_pnl=Decimal("0"),
                            opened_at=bar.open_time,
                            strategy_name=self.strategy.name,
                            stop_loss=signal.suggested_stop,
                            take_profit=signal.suggested_target,
                        )
                        open_trade = BacktestTrade(
                            symbol=bar.symbol,
                            side="buy",
                            entry_time=bar.open_time,
                            exit_time=None,
                            entry_price=fill["price"],
                            exit_price=None,
                            quantity=qty,
                            fees=fees,
                            slippage_cost=slip,
                            reason=signal.entry_rationale,
                        )
                        bars_held = 0

            elif (
                signal.direction in (SignalDirection.EXIT, SignalDirection.SELL)
                and position
            ):
                fill = self._apply_costs(mark, side=OrderSide.SELL)
                proceeds = fill["price"] * position.quantity
                fees = fill["fee"] * position.quantity
                slip = fill["slippage_cost"] * position.quantity
                cash += proceeds - fees
                pnl = (fill["price"] - position.entry_price) * position.quantity - fees
                if open_trade:
                    open_trade.exit_time = bar.open_time
                    open_trade.exit_price = fill["price"]
                    open_trade.pnl = pnl
                    open_trade.fees += fees
                    open_trade.slippage_cost += slip
                    open_trade.reason = signal.entry_rationale
                    trades.append(open_trade)
                position = None
                open_trade = None
                bars_held = 0

            # Hard stop / take-profit check on same bar after signal (using bar low/high)
            if position is not None:
                exited = False
                exit_price = None
                reason = ""
                if position.stop_loss is not None and bar.low <= position.stop_loss:
                    exit_price = position.stop_loss
                    reason = "stop-loss"
                    exited = True
                elif (
                    position.take_profit is not None
                    and bar.high >= position.take_profit
                ):
                    exit_price = position.take_profit
                    reason = "take-profit"
                    exited = True
                if exited and exit_price is not None:
                    fill = self._apply_costs(exit_price, side=OrderSide.SELL)
                    proceeds = fill["price"] * position.quantity
                    fees = fill["fee"] * position.quantity
                    slip = fill["slippage_cost"] * position.quantity
                    cash += proceeds - fees
                    pnl = (
                        fill["price"] - position.entry_price
                    ) * position.quantity - fees
                    if open_trade:
                        open_trade.exit_time = bar.open_time
                        open_trade.exit_price = fill["price"]
                        open_trade.pnl = pnl
                        open_trade.fees += fees
                        open_trade.slippage_cost += slip
                        open_trade.reason = reason
                        trades.append(open_trade)
                    position = None
                    open_trade = None
                    bars_held = 0

        # Force close at end
        if position is not None:
            mark = candles[-1].close
            fill = self._apply_costs(mark, side=OrderSide.SELL)
            proceeds = fill["price"] * position.quantity
            fees = fill["fee"] * position.quantity
            slip = fill["slippage_cost"] * position.quantity
            cash += proceeds - fees
            pnl = (fill["price"] - position.entry_price) * position.quantity - fees
            if open_trade:
                open_trade.exit_time = candles[-1].open_time
                open_trade.exit_price = fill["price"]
                open_trade.pnl = pnl
                open_trade.fees += fees
                open_trade.slippage_cost += slip
                open_trade.reason = "end-of-data"
                trades.append(open_trade)

        final_equity = cash
        metrics = compute_metrics(
            trades=trades,
            equity_curve=equity_curve,
            initial_cash=self.config.initial_cash,
            final_equity=final_equity,
        )
        result = BacktestResult(
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            config={
                "initial_cash": str(self.config.initial_cash),
                "fee_rate": str(self.config.fee_rate),
                "slippage_rate": str(self.config.slippage_rate),
                "spread_rate": str(self.config.spread_rate),
                "position_size_fraction": str(self.config.position_size_fraction),
                "strategy_params": cfg.params,
            },
            strategy_id=self.strategy.strategy_id,
        )
        if write_reports:
            self.config.report_dir.mkdir(parents=True, exist_ok=True)
            result.json_path = write_json_report(result, self.config.report_dir)
            result.markdown_path = write_markdown_summary(
                result, self.config.report_dir
            )
        return result

    def _size_position(self, cash: Decimal, price: Decimal) -> Decimal:
        notional = cash * self.config.position_size_fraction
        if price <= 0:
            return Decimal("0")
        return (notional / price).quantize(Decimal("0.00000001"))

    def _apply_costs(self, price: Decimal, *, side: OrderSide) -> dict[str, Decimal]:
        half_spread = price * self.config.spread_rate / Decimal("2")
        slip = price * self.config.slippage_rate
        if side == OrderSide.BUY:
            fill_price = price + half_spread + slip
        else:
            fill_price = price - half_spread - slip
        fee = fill_price * self.config.fee_rate
        return {
            "price": fill_price,
            "fee": fee,
            "slippage_cost": slip,
        }


def candle_fingerprint(candles: list[Candle]) -> str:
    payload = json.dumps(
        [
            {
                "t": c.open_time.isoformat(),
                "c": str(c.close),
                "v": str(c.volume),
            }
            for c in candles
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()
