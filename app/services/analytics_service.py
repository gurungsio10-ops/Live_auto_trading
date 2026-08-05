"""Paper-trading analytics computed from persisted snapshots and closed positions."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.ops import ClosedPositionORM
from app.models.database.portfolio import PortfolioSnapshotORM
from app.services.paper_session import get_paper_session


def _d(value: object) -> Decimal:
    return Decimal(str(value))


def _safe_div(num: Decimal, den: Decimal) -> Decimal | None:
    if den == 0:
        return None
    return num / den


async def compute_paper_analytics(db: AsyncSession) -> dict[str, Any]:
    """Truthful paper metrics. Labels insufficient data; never annualises short samples."""
    session = get_paper_session()
    summary = session.portfolio_summary()
    starting = session.settings.paper_starting_balance
    equity = _d(summary["equity"])
    realized = _d(summary["realized_pnl"])
    unrealized = _d(summary["unrealized_pnl"])
    total_return = _safe_div(equity - starting, starting)

    snaps = (
        await db.scalars(
            select(PortfolioSnapshotORM).order_by(PortfolioSnapshotORM.created_at.asc())
        )
    ).all()
    fees_paid = snaps[-1].fees_paid if snaps else Decimal("0")
    max_dd = max((s.drawdown for s in snaps), default=_d(summary["drawdown"]))

    closed = (await db.scalars(select(ClosedPositionORM))).all()
    # Fall back to in-memory filled sells as trade proxies when closed_positions empty.
    wins = [c for c in closed if c.realized_pnl > 0]
    losses = [c for c in closed if c.realized_pnl < 0]
    flats = [c for c in closed if c.realized_pnl == 0]
    trade_count = len(closed)

    if trade_count == 0:
        # Use order history filled sells as weak proxy — mark insufficient.
        filled_sells = [
            o
            for o in session.order_history
            if o.side.value == "sell"
            and o.status.value in {"FILLED", "PARTIALLY_FILLED"}
        ]
        trade_count_proxy = len(filled_sells)
        insufficient = True
        win_rate = None
        profit_factor = None
        avg_win = None
        avg_loss = None
        expectancy = None
        winning = 0
        losing = 0
        avg_hold = None
    else:
        insufficient = trade_count < 5
        winning = len(wins)
        losing = len(losses)
        win_rate = _safe_div(Decimal(winning), Decimal(trade_count))
        gross_win = sum((w.realized_pnl for w in wins), Decimal("0"))
        gross_loss = abs(sum((x.realized_pnl for x in losses), Decimal("0")))
        profit_factor = _safe_div(gross_win, gross_loss) if gross_loss > 0 else None
        avg_win = _safe_div(gross_win, Decimal(winning)) if winning else None
        avg_loss = _safe_div(gross_loss, Decimal(losing)) if losing else None
        avg_pnl = _safe_div(
            sum((c.realized_pnl for c in closed), Decimal("0")), Decimal(trade_count)
        )
        expectancy = avg_pnl
        hold_secs = [
            (c.closed_at - c.opened_at).total_seconds()
            for c in closed
            if c.closed_at and c.opened_at
        ]
        avg_hold = (
            str(Decimal(str(sum(hold_secs) / len(hold_secs))).quantize(Decimal("0.01")))
            if hold_secs
            else None
        )
        trade_count_proxy = trade_count

    exposure_by_symbol = {
        p["symbol"]: {
            "quantity": p["quantity"],
            "notional": str(
                (_d(p["quantity"]) * _d(p["current_price"])).quantize(Decimal("0.01"))
            ),
            "unrealized_pnl": p["unrealized_pnl"],
        }
        for p in session.positions()
    }

    def fmt(v: Decimal | None) -> str | None:
        return None if v is None else str(v)

    return {
        "starting_balance": str(starting),
        "current_equity": str(equity),
        "total_return": fmt(total_return),
        "realized_pnl": str(realized),
        "unrealized_pnl": str(unrealized),
        "fees_paid": str(fees_paid),
        "maximum_drawdown": str(max_dd),
        "win_rate": fmt(win_rate),
        "profit_factor": fmt(profit_factor),
        "average_win": fmt(avg_win),
        "average_loss": fmt(avg_loss),
        "expectancy": fmt(expectancy),
        "total_trades": trade_count_proxy,
        "winning_trades": winning if trade_count != 0 else 0,
        "losing_trades": losing if trade_count != 0 else 0,
        "flat_trades": len(flats) if closed else 0,
        "average_holding_seconds": avg_hold,
        "exposure_by_symbol": exposure_by_symbol,
        "insufficient_data": insufficient,
        "notes": [
            "Paper trading only — simulated results do not guarantee future performance.",
            "Metrics are not annualised for short samples.",
            "Insufficient data flagged when fewer than 5 closed positions exist."
            if insufficient
            else "Closed-position sample size is adequate for descriptive stats.",
        ],
    }
