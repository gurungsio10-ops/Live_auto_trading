"""Portfolio state helpers."""

from __future__ import annotations

from decimal import Decimal

from app.models.domain.trading import PortfolioState, Position


class PortfolioService:
    def __init__(
        self,
        *,
        cash: Decimal = Decimal("10000"),
        positions: list[Position] | None = None,
        realized_pnl: Decimal = Decimal("0"),
        daily_pnl: Decimal = Decimal("0"),
        consecutive_losses: int = 0,
    ) -> None:
        self.cash = cash
        self.positions = {p.symbol: p for p in (positions or [])}
        self.realized_pnl = realized_pnl
        self.daily_pnl = daily_pnl
        self.consecutive_losses = consecutive_losses
        self.peak_equity = cash

    def snapshot(self) -> PortfolioState:
        unrealized = sum(
            (p.unrealized_pnl for p in self.positions.values()), Decimal("0")
        )
        equity = self.cash + sum(
            (p.quantity * p.current_price for p in self.positions.values()),
            Decimal("0"),
        )
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = (
            (self.peak_equity - equity) / self.peak_equity
            if self.peak_equity > 0
            else Decimal("0")
        )
        return PortfolioState(
            cash_balance=self.cash,
            equity=equity,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=unrealized,
            daily_pnl=self.daily_pnl,
            peak_equity=self.peak_equity,
            drawdown=drawdown,
            open_positions=list(self.positions.values()),
            consecutive_losses=self.consecutive_losses,
        )
