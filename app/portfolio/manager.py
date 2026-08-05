"""
PortfolioManager — production paper portfolio views.

Wraps PaperSession / PaperTradingEngine state. Does not create a parallel ledger.
Leverage/margin fields are reported as spot-paper constants (1x / n/a).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.core.time import ensure_utc, utc_now
from app.portfolio.service import PortfolioService
from app.services.paper_session import PaperSession, get_paper_session


class PortfolioManager:
    """Synchronizes dashboard portfolio metrics from the paper runtime SSOT."""

    def __init__(self, session: PaperSession | None = None) -> None:
        self.session = session or get_paper_session()

    def _equity(self) -> Decimal:
        paper = self.session.paper
        marked = sum(
            (p.quantity * p.current_price for p in paper.state.positions.values()),
            Decimal("0"),
        )
        return paper.state.cash + paper.state.reserved_cash + marked

    def _period_pnl(self, *, days: int) -> Decimal:
        """Approximate period PnL from equity curve points within the window."""
        cutoff = utc_now() - timedelta(days=days)
        points = self.session.equity_points()
        if not points:
            return Decimal("0")
        in_window = [
            p
            for p in points
            if ensure_utc(datetime.fromisoformat(str(p["time"]).replace("Z", "+00:00")))
            >= cutoff
        ]
        if len(in_window) < 2:
            # Fall back to daily_pnl for 1d when curve is thin.
            if days <= 1:
                return Decimal(
                    str(self.session.portfolio_summary().get("daily_pnl", "0"))
                )
            return Decimal("0")
        start = Decimal(str(in_window[0]["equity"]))
        end = Decimal(str(in_window[-1]["equity"]))
        return end - start

    def snapshot(self) -> dict[str, Any]:
        summary = self.session.portfolio_summary()
        equity = self._equity()
        cash = self.session.paper.state.cash
        reserved = self.session.paper.state.reserved_cash
        positions = self.session.positions()
        exposure = sum(
            (
                abs(Decimal(str(p["quantity"])) * Decimal(str(p["current_price"])))
                for p in positions
            ),
            Decimal("0"),
        )
        allocation = {
            p["symbol"]: str(
                (
                    Decimal(str(p["quantity"]))
                    * Decimal(str(p["current_price"]))
                    / equity
                ).quantize(Decimal("0.0001"))
                if equity > 0
                else Decimal("0")
            )
            for p in positions
        }
        return {
            **summary,
            "available_balance": str(cash),
            "reserved_capital": str(reserved),
            "margin_balance": str(cash),  # spot paper — available capital only
            "leverage": "1",
            "margin_mode": "spot_paper",
            "exposure": str(exposure.quantize(Decimal("0.01"))),
            "exposure_pct": str(
                (exposure / equity).quantize(Decimal("0.0001"))
                if equity > 0
                else Decimal("0")
            ),
            "daily_pnl": summary.get("daily_pnl"),
            "weekly_pnl": str(self._period_pnl(days=7).quantize(Decimal("0.01"))),
            "monthly_pnl": str(self._period_pnl(days=30).quantize(Decimal("0.01"))),
            "allocation": allocation,
            "position_count": len(positions),
            "equity_curve_points": len(self.session.equity_points()),
            "synced_with": "paper_session_checkpoint",
            "banner": "PAPER TRADING — NO REAL FUNDS",
        }

    def to_portfolio_service(self) -> PortfolioService:
        paper = self.session.paper
        return PortfolioService(
            cash=paper.state.cash,
            positions=list(paper.state.positions.values()),
            realized_pnl=paper.state.realized_pnl,
            daily_pnl=Decimal(
                str(self.session.portfolio_summary().get("daily_pnl", "0"))
            ),
            consecutive_losses=int(
                self.session.portfolio_summary().get("consecutive_losses", 0)
            ),
        )


def get_portfolio_manager() -> PortfolioManager:
    return PortfolioManager()
