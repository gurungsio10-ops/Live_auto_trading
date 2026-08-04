"""
Durable paper-session persistence (kill switch, portfolio, cycle keys).

Uses ``system_state``, ``balances``, ``positions``, ``portfolio_snapshots``,
and ``trade_journal`` tables from Alembic ``0004``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.time import utc_now
from app.models.database.portfolio import (
    BalanceORM,
    PortfolioSnapshotORM,
    PositionORM,
    SystemStateORM,
    TradeJournalORM,
)
from app.models.domain.trading import Position

logger = get_logger("paper.persistence")

KEY_KILL_SWITCH = "kill_switch"
KEY_PAPER_CHECKPOINT = "paper_checkpoint"
KEY_CYCLE_KEYS = "processed_cycle_keys"
KEY_RUNTIME = "runtime_mode"


def _dec(value: object) -> Decimal:
    return Decimal(str(value))


async def get_system_value(session: AsyncSession, key: str) -> dict[str, Any] | None:
    row = await session.get(SystemStateORM, key)
    return None if row is None else dict(row.value or {})


async def set_system_value(
    session: AsyncSession, key: str, value: dict[str, Any]
) -> None:
    row = await session.get(SystemStateORM, key)
    now = utc_now()
    if row is None:
        session.add(SystemStateORM(key=key, value=value, updated_at=now))
    else:
        row.value = value
        row.updated_at = now
    await session.commit()


async def save_kill_switch(session: AsyncSession, *, enabled: bool) -> None:
    await set_system_value(
        session,
        KEY_KILL_SWITCH,
        {"enabled": enabled, "updated_at": utc_now().isoformat()},
    )


async def load_kill_switch(session: AsyncSession) -> bool | None:
    value = await get_system_value(session, KEY_KILL_SWITCH)
    if value is None:
        return None
    return bool(value.get("enabled"))


async def save_cycle_keys(
    session: AsyncSession, keys: set[tuple[str, str, str, str]]
) -> None:
    """Persist processed cycle keys as ISO-string tuples."""
    payload = {
        "keys": [list(k) for k in sorted(keys)],
        "updated_at": utc_now().isoformat(),
    }
    await set_system_value(session, KEY_CYCLE_KEYS, payload)


async def load_cycle_keys(session: AsyncSession) -> set[tuple[str, str, str, str]]:
    value = await get_system_value(session, KEY_CYCLE_KEYS)
    if not value:
        return set()
    out: set[tuple[str, str, str, str]] = set()
    for item in value.get("keys") or []:
        if isinstance(item, (list, tuple)) and len(item) == 4:
            out.add((str(item[0]), str(item[1]), str(item[2]), str(item[3])))
    return out


async def save_paper_checkpoint(
    session: AsyncSession,
    *,
    cash: Decimal,
    positions: dict[str, Position],
    realized_pnl: Decimal,
    peak_equity: Decimal,
    consecutive_losses: int,
    idempotency_index: dict[str, str],
    fees_paid: Decimal = Decimal("0"),
    correlation_id: str | None = None,
) -> None:
    now = utc_now()
    # Upsert USDT balance
    bal = (
        await session.execute(select(BalanceORM).where(BalanceORM.asset == "USDT"))
    ).scalar_one_or_none()
    if bal is None:
        session.add(
            BalanceORM(
                id=uuid4().hex,
                asset="USDT",
                free=cash,
                locked=Decimal("0"),
                as_of=now,
            )
        )
    else:
        bal.free = cash
        bal.as_of = now

    # Replace positions
    existing = (await session.execute(select(PositionORM))).scalars().all()
    for row in existing:
        await session.delete(row)
    for symbol, pos in positions.items():
        session.add(
            PositionORM(
                id=uuid4().hex,
                symbol=symbol,
                quantity=pos.quantity,
                entry_price=pos.entry_price,
                current_price=pos.current_price,
                unrealized_pnl=pos.unrealized_pnl,
                realized_pnl=getattr(pos, "realized_pnl", Decimal("0")) or Decimal("0"),
                opened_at=pos.opened_at or now,
                strategy_name=pos.strategy_name,
                updated_at=now,
            )
        )

    equity = cash + sum((p.quantity * p.current_price) for p in positions.values())
    unrealized = equity - cash
    session.add(
        PortfolioSnapshotORM(
            id=uuid4().hex,
            cash_balance=cash,
            equity=equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized,
            daily_pnl=equity - cash,  # relative; refined by session daily start
            peak_equity=peak_equity,
            drawdown=(
                (peak_equity - equity) / peak_equity
                if peak_equity > 0
                else Decimal("0")
            ),
            fees_paid=fees_paid,
            exposure=unrealized,
            correlation_id=correlation_id,
            payload={"source": "paper_checkpoint"},
            created_at=now,
        )
    )

    await set_system_value(
        session,
        KEY_PAPER_CHECKPOINT,
        {
            "cash": str(cash),
            "realized_pnl": str(realized_pnl),
            "peak_equity": str(peak_equity),
            "consecutive_losses": consecutive_losses,
            "idempotency_index": dict(idempotency_index),
            "positions": {
                symbol: {
                    "quantity": str(pos.quantity),
                    "entry_price": str(pos.entry_price),
                    "current_price": str(pos.current_price),
                    "unrealized_pnl": str(pos.unrealized_pnl),
                    "opened_at": (pos.opened_at or now).isoformat(),
                    "strategy_name": pos.strategy_name,
                }
                for symbol, pos in positions.items()
            },
            "updated_at": now.isoformat(),
        },
    )
    await session.commit()


async def load_paper_checkpoint(session: AsyncSession) -> dict[str, Any] | None:
    return await get_system_value(session, KEY_PAPER_CHECKPOINT)


async def append_audit_event(
    session: AsyncSession,
    *,
    event_type: str,
    message: str,
    severity: str = "info",
    correlation_id: str | None = None,
    order_id: str | None = None,
    idempotency_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        TradeJournalORM(
            id=uuid4().hex,
            event_type=event_type,
            severity=severity,
            message=message,
            correlation_id=correlation_id,
            strategy_run_id=None,
            order_id=order_id,
            idempotency_key=idempotency_key,
            payload=payload or {},
            created_at=utc_now(),
        )
    )
    await session.commit()


async def list_audit_events(
    session: AsyncSession, *, limit: int = 50
) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(TradeJournalORM)
                .order_by(TradeJournalORM.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "severity": r.severity,
            "message": r.message,
            "correlation_id": r.correlation_id,
            "order_id": r.order_id,
            "idempotency_key": r.idempotency_key,
            "payload": r.payload,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def checkpoint_to_positions(payload: dict[str, Any]) -> dict[str, Position]:
    from datetime import datetime

    positions: dict[str, Position] = {}
    raw = payload.get("positions") or {}
    for symbol, data in raw.items():
        opened = data.get("opened_at")
        opened_at = (
            datetime.fromisoformat(opened.replace("Z", "+00:00"))
            if isinstance(opened, str)
            else utc_now()
        )
        positions[symbol] = Position(
            symbol=symbol,
            quantity=_dec(data["quantity"]),
            entry_price=_dec(data["entry_price"]),
            current_price=_dec(data["current_price"]),
            unrealized_pnl=_dec(data.get("unrealized_pnl") or "0"),
            opened_at=opened_at,
            strategy_name=data.get("strategy_name"),
        )
    return positions
