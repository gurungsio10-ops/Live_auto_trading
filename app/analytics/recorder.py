"""Record closed paper trades into the durable performance journal."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.analytics.trade_journal import (
    ClosedTrade,
    TradeJournalService,
    build_closed_trade_from_exit,
    classify_market_regime,
    risk_score_from_context,
)
from app.core.logging import get_logger
from app.models.domain.enums import OrderSide, OrderStatus
from app.models.domain.trading import Fill, Order, Position

log = get_logger("analytics.recorder")


def maybe_build_closed_trade(
    *,
    position_before: Position | None,
    order: Order,
    fills: list[Fill],
    fee_rate: Decimal,
    slippage_rate: Decimal,
    paper_session_id: str,
    exit_reason: str = "signal_exit",
    drawdown: Decimal = Decimal("0"),
    consecutive_losses: int = 0,
    kill_switch: bool = False,
    market_regime: str | None = None,
    correlation_id: str | None = None,
    rsi: Decimal | None = None,
) -> list[ClosedTrade]:
    """Build closed-trade records for new SELL fills against a prior position."""
    if position_before is None:
        return []
    if order.side != OrderSide.SELL:
        return []
    if order.status not in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
        return []
    regime = market_regime or classify_market_regime(rsi=rsi)
    score = risk_score_from_context(
        drawdown=drawdown,
        consecutive_losses=consecutive_losses,
        kill_switch=kill_switch,
    )
    # Only fills belonging to this order, newest last.
    order_fills = [f for f in fills if f.order_id == order.id]
    if not order_fills:
        return []
    trades: list[ClosedTrade] = []
    for fill in order_fills:
        trades.append(
            build_closed_trade_from_exit(
                position=position_before,
                order=order,
                fill=fill,
                fee_rate=fee_rate,
                slippage_rate=slippage_rate,
                paper_session_id=paper_session_id,
                exit_reason=exit_reason,
                risk_score=score,
                market_regime=regime,
                correlation_id=correlation_id,
            )
        )
    return trades


async def persist_closed_trades(trades: list[ClosedTrade]) -> int:
    """Best-effort durable write; returns number of newly inserted rows."""
    if not trades:
        return 0
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.db.base import create_engine

    engine = create_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    inserted = 0
    try:
        async with factory() as session:
            journal = TradeJournalService(session)
            for trade in trades:
                if await journal.record(trade, commit=False):
                    inserted += 1
            if inserted:
                await session.commit()
                log.info(
                    "closed_trades_recorded",
                    extra={"inserted": inserted, "attempted": len(trades)},
                )
    except Exception as exc:
        log.warning(
            "closed_trades_persist_failed",
            extra={"error": str(exc), "attempted": len(trades)},
        )
    finally:
        await engine.dispose()
    return inserted


async def persist_closed_trades_in_session(
    session: Any, trades: list[ClosedTrade]
) -> int:
    if not trades:
        return 0
    journal = TradeJournalService(session)
    inserted = 0
    for trade in trades:
        if await journal.record(trade, commit=False):
            inserted += 1
    return inserted
