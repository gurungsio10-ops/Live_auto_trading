"""Repository for durable paper-trading portfolio state."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.database.portfolio import (
    BalanceORM,
    PortfolioSnapshotORM,
    PositionORM,
    SystemStateORM,
    TradeJournalORM,
)
from app.models.domain.trading import Position


class PaperStateRepository:
    """Transactional load/save for paper balances, positions, snapshots, flags."""

    CASH_ASSET = "USDT"
    FLAGS_KEY = "paper_session_flags"
    ACCOUNT_KEY = "paper_account"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load_cash(self) -> Decimal | None:
        row = await self.session.scalar(
            select(BalanceORM).where(BalanceORM.asset == self.CASH_ASSET)
        )
        return row.free if row else None

    async def load_positions(self) -> list[Position]:
        rows = (await self.session.scalars(select(PositionORM))).all()
        return [
            Position(
                symbol=r.symbol,
                quantity=r.quantity,
                entry_price=r.entry_price,
                current_price=r.current_price,
                unrealized_pnl=r.unrealized_pnl,
                realized_pnl=r.realized_pnl,
                opened_at=r.opened_at,
                strategy_name=r.strategy_name,
            )
            for r in rows
        ]

    async def load_flags(self) -> dict[str, Any]:
        row = await self.session.get(SystemStateORM, self.FLAGS_KEY)
        return dict(row.value) if row else {}

    async def load_equity_curve(self, *, limit: int = 500) -> list[dict[str, str]]:
        rows = (
            await self.session.scalars(
                select(PortfolioSnapshotORM)
                .order_by(PortfolioSnapshotORM.created_at.asc())
                .limit(limit)
            )
        ).all()
        return [
            {
                "time": r.created_at.isoformat(),
                "equity": str(r.equity),
                "drawdown": str(r.drawdown),
            }
            for r in rows
        ]

    async def replace_balances_and_positions(
        self,
        *,
        cash: Decimal,
        positions: dict[str, Position],
        realized_pnl: Decimal,
    ) -> None:
        if cash < 0:
            raise ValueError("cash balance cannot be negative")
        now = utc_now()
        await self.session.execute(delete(BalanceORM))
        await self.session.execute(delete(PositionORM))
        self.session.add(
            BalanceORM(
                id=uuid4().hex,
                asset=self.CASH_ASSET,
                free=cash,
                locked=Decimal("0"),
                as_of=now,
            )
        )
        for symbol, pos in positions.items():
            if pos.quantity < 0:
                raise ValueError(f"invalid quantity for {symbol}")
            if pos.entry_price < 0 or pos.current_price < 0:
                raise ValueError(f"invalid price for {symbol}")
            self.session.add(
                PositionORM(
                    id=uuid4().hex,
                    symbol=symbol,
                    quantity=pos.quantity,
                    entry_price=pos.entry_price,
                    current_price=pos.current_price,
                    unrealized_pnl=pos.unrealized_pnl,
                    realized_pnl=pos.realized_pnl,
                    opened_at=pos.opened_at,
                    strategy_name=pos.strategy_name,
                    updated_at=now,
                )
            )
        await self._upsert_system(
            self.ACCOUNT_KEY,
            {
                "realized_pnl": str(realized_pnl),
                "cash": str(cash),
                "updated_at": now.isoformat(),
            },
        )

    async def save_snapshot(
        self,
        *,
        cash: Decimal,
        equity: Decimal,
        realized_pnl: Decimal,
        unrealized_pnl: Decimal,
        daily_pnl: Decimal,
        peak_equity: Decimal,
        drawdown: Decimal,
        fees_paid: Decimal,
        exposure: Decimal,
        correlation_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        sid = uuid4().hex
        self.session.add(
            PortfolioSnapshotORM(
                id=sid,
                cash_balance=cash,
                equity=equity,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                daily_pnl=daily_pnl,
                peak_equity=peak_equity,
                drawdown=drawdown,
                fees_paid=fees_paid,
                exposure=exposure,
                correlation_id=correlation_id,
                payload=payload or {},
                created_at=utc_now(),
            )
        )
        return sid

    async def save_flags(self, flags: dict[str, Any]) -> None:
        await self._upsert_system(self.FLAGS_KEY, flags)

    async def append_journal(
        self,
        *,
        event_type: str,
        message: str,
        severity: str = "info",
        correlation_id: str | None = None,
        order_id: str | None = None,
        idempotency_key: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        jid = uuid4().hex
        self.session.add(
            TradeJournalORM(
                id=jid,
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
        return jid

    async def list_journal(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        rows = (
            await self.session.scalars(
                select(TradeJournalORM)
                .order_by(TradeJournalORM.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [
            {
                "id": r.id,
                "event_type": r.event_type,
                "severity": r.severity,
                "message": r.message,
                "correlation_id": r.correlation_id,
                "order_id": r.order_id,
                "created_at": r.created_at.isoformat(),
                "payload": r.payload,
            }
            for r in rows
        ]

    async def _upsert_system(self, key: str, value: dict[str, Any]) -> None:
        row = await self.session.get(SystemStateORM, key)
        now = utc_now()
        if row is None:
            self.session.add(SystemStateORM(key=key, value=value, updated_at=now))
        else:
            row.value = value
            row.updated_at = now
