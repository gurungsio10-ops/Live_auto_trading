"""Durable hydrate/persist for PaperSession against the database."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db import base as db_base
from app.models.database.ops import ClosedPositionORM, PaperCycleRunORM
from app.models.domain.trading import Order
from app.repositories.paper_state_repository import PaperStateRepository

if TYPE_CHECKING:
    from app.services.paper_session import PaperSession

logger = logging.getLogger(__name__)


def _sessions():
    return db_base.SessionLocal


async def hydrate_paper_session(
    session: PaperSession, db: AsyncSession | None = None
) -> bool:
    """Load durable state into an in-memory PaperSession. Returns True if restored."""
    own = db is None
    if own:
        db = _sessions()()
    assert db is not None
    try:
        repo = PaperStateRepository(db)
        cash = await repo.load_cash()
        if cash is None:
            # Seed initial durable row so restarts have a baseline.
            await repo.replace_balances_and_positions(
                cash=session.paper.state.cash,
                positions=dict(session.paper.state.positions),
                realized_pnl=session.paper.state.realized_pnl,
            )
            await repo.save_flags(
                {
                    "kill_switch_enabled": session.kill_switch_enabled,
                    "trading_paused": session.trading_paused,
                    "selected_strategy_id": session.selected_strategy_id,
                    "peak_equity": str(session._peak_equity),
                    "daily_start_equity": str(session._daily_start_equity),
                    "consecutive_losses": session._consecutive_losses,
                }
            )
            await repo.save_snapshot(
                cash=session.paper.state.cash,
                equity=session.paper.state.cash,
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                daily_pnl=Decimal("0"),
                peak_equity=session._peak_equity,
                drawdown=Decimal("0"),
                fees_paid=Decimal("0"),
                exposure=Decimal("0"),
                payload={"source": "seed"},
            )
            await db.commit()
            return False

        positions = await repo.load_positions()
        flags = await repo.load_flags()
        curve = await repo.load_equity_curve()

        with session._lock:
            session.paper.state.cash = cash
            session.paper.state.positions = {p.symbol: p for p in positions}
            session.paper.state.realized_pnl = Decimal(
                str(flags.get("realized_pnl") or session.paper.state.realized_pnl)
            )
            session.kill_switch_enabled = bool(
                flags.get("kill_switch_enabled", session.kill_switch_enabled)
            )
            session.trading_paused = bool(flags.get("trading_paused", False))
            session.selected_strategy_id = flags.get(
                "selected_strategy_id", session.selected_strategy_id
            )
            if "peak_equity" in flags:
                session._peak_equity = Decimal(str(flags["peak_equity"]))
            if "daily_start_equity" in flags:
                session._daily_start_equity = Decimal(str(flags["daily_start_equity"]))
            if "consecutive_losses" in flags:
                session._consecutive_losses = int(flags["consecutive_losses"])
            if curve:
                session.equity_curve = curve
            for pos in positions:
                session.paper.set_mark_price(pos.symbol, pos.current_price)
        logger.info(
            "paper_session_hydrated",
            extra={"cash": str(cash), "positions": len(positions)},
        )
        return True
    finally:
        if own:
            await db.close()


async def persist_paper_session(
    session: PaperSession,
    *,
    correlation_id: str | None = None,
    journal_message: str | None = None,
    order: Order | None = None,
    db: AsyncSession | None = None,
) -> None:
    """Transactionally persist balances, positions, snapshot and optional journal row."""
    own = db is None
    if own:
        db = _sessions()()
    assert db is not None
    try:
        repo = PaperStateRepository(db)
        with session._lock:
            cash = session.paper.state.cash
            positions = dict(session.paper.state.positions)
            realized = session.paper.state.realized_pnl
            summary = session.portfolio_summary()
            fees = sum((o.fees for o in session.order_history), Decimal("0"))
            exposure = sum(
                (p.quantity * p.current_price for p in positions.values()),
                Decimal("0"),
            )
            flags = {
                "kill_switch_enabled": session.kill_switch_enabled,
                "trading_paused": session.trading_paused,
                "selected_strategy_id": session.selected_strategy_id,
                "peak_equity": str(session._peak_equity),
                "daily_start_equity": str(session._daily_start_equity),
                "consecutive_losses": session._consecutive_losses,
                "realized_pnl": str(realized),
            }

        await repo.replace_balances_and_positions(
            cash=cash, positions=positions, realized_pnl=realized
        )
        await repo.save_flags(flags)
        await repo.save_snapshot(
            cash=Decimal(summary["cash_balance"]),
            equity=Decimal(summary["equity"]),
            realized_pnl=Decimal(summary["realized_pnl"]),
            unrealized_pnl=Decimal(summary["unrealized_pnl"]),
            daily_pnl=Decimal(summary["daily_pnl"]),
            peak_equity=Decimal(summary["peak_equity"]),
            drawdown=Decimal(summary["drawdown"]),
            fees_paid=fees,
            exposure=exposure,
            correlation_id=correlation_id,
            payload={"source": "persist"},
        )
        if journal_message:
            await repo.append_journal(
                event_type="PAPER_STATE_PERSISTED",
                message=journal_message,
                correlation_id=correlation_id,
                order_id=order.id if order else None,
                idempotency_key=order.idempotency_key if order else None,
                payload={"equity": summary["equity"]},
            )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("paper_session_persist_failed")
        raise
    finally:
        if own:
            await db.close()


async def record_cycle_run(
    *,
    correlation_id: str,
    symbol: str,
    timeframe: str,
    strategy_id: str,
    status: str,
    idempotency_key: str | None = None,
    signal_direction: str | None = None,
    order_id: str | None = None,
    risk_decision: str | None = None,
    risk_reason_code: str | None = None,
    duration_ms: int | None = None,
    error_summary: str | None = None,
    payload: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
) -> str:
    own = db is None
    if own:
        db = _sessions()()
    assert db is not None
    run_id = uuid4().hex
    try:
        if idempotency_key:
            from sqlalchemy import select

            existing = await db.scalar(
                select(PaperCycleRunORM).where(
                    PaperCycleRunORM.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                return existing.id
        db.add(
            PaperCycleRunORM(
                id=run_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                symbol=symbol,
                timeframe=timeframe,
                strategy_id=strategy_id,
                status=status,
                signal_direction=signal_direction,
                order_id=order_id,
                risk_decision=risk_decision,
                risk_reason_code=risk_reason_code,
                duration_ms=duration_ms,
                error_summary=error_summary,
                payload=payload or {},
                created_at=utc_now(),
            )
        )
        await db.commit()
        return run_id
    except Exception:
        await db.rollback()
        raise
    finally:
        if own:
            await db.close()


async def record_closed_position(
    *,
    symbol: str,
    quantity: Decimal,
    entry_price: Decimal,
    exit_price: Decimal,
    realized_pnl: Decimal,
    fees: Decimal = Decimal("0"),
    strategy_name: str | None = None,
    opened_at: Any = None,
    correlation_id: str | None = None,
    db: AsyncSession | None = None,
) -> None:
    own = db is None
    if own:
        db = _sessions()()
    assert db is not None
    try:
        db.add(
            ClosedPositionORM(
                id=uuid4().hex,
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                exit_price=exit_price,
                realized_pnl=realized_pnl,
                fees=fees,
                strategy_name=strategy_name,
                opened_at=opened_at or utc_now(),
                closed_at=utc_now(),
                correlation_id=correlation_id,
                payload={},
            )
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        if own:
            await db.close()
