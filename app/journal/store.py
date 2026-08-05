"""Trade journal — persist signals, risk decisions, orders, fills, events."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, Numeric, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base
from app.models.domain.enums import RiskDecision, RiskReasonCode, SignalDirection
from app.models.domain.trading import Fill, Order, RiskEvaluation, TradeSignal


class SignalORM(Base):
    __tablename__ = "signals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(128))
    strategy_version: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    direction: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    entry_rationale: Mapped[str] = mapped_column(Text)
    invalidation_condition: Mapped[str] = mapped_column(Text)
    suggested_stop: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    suggested_target: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    input_data_fingerprint: Mapped[str] = mapped_column(String(256))
    led_to_order: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class RiskDecisionORM(Base):
    __tablename__ = "risk_decisions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_idempotency_key: Mapped[str] = mapped_column(String(128))
    decision: Mapped[str] = mapped_column(String(32))
    reason_code: Mapped[str] = mapped_column(String(64))
    approved_quantity: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    message: Mapped[str] = mapped_column(Text, default="")
    checks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrderORM(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    order_type: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=0)
    price: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    average_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    status: Mapped[str] = mapped_column(String(32))
    strategy_name: Mapped[str | None] = mapped_column(String(128))
    signal_id: Mapped[str | None] = mapped_column(String(64))
    risk_decision: Mapped[str | None] = mapped_column(String(32))
    risk_reason_code: Mapped[str | None] = mapped_column(String(64))
    fees: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class FillORM(Base):
    __tablename__ = "fills"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    price: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    fee: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SystemEventORM(Base):
    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JournalStore:
    """Persist full reconstructable trade audit trail."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_signal(
        self, signal: TradeSignal, *, order_id: str | None = None
    ) -> str:
        sid = uuid4().hex
        self.session.add(
            SignalORM(
                id=sid,
                strategy_name=signal.strategy_name,
                strategy_version=signal.strategy_version,
                symbol=signal.symbol,
                timestamp=signal.timestamp,
                direction=(
                    signal.direction.value
                    if isinstance(signal.direction, SignalDirection)
                    else str(signal.direction)
                ),
                confidence=signal.confidence,
                entry_rationale=signal.entry_rationale,
                invalidation_condition=signal.invalidation_condition,
                suggested_stop=signal.suggested_stop,
                suggested_target=signal.suggested_target,
                input_data_fingerprint=(signal.input_data_fingerprint or "")[:256],
                led_to_order=order_id,
                payload=signal.metadata,
            )
        )
        await self.session.commit()
        return sid

    async def record_risk_decision(
        self, *, idempotency_key: str, evaluation: RiskEvaluation
    ) -> str:
        rid = uuid4().hex
        self.session.add(
            RiskDecisionORM(
                id=rid,
                order_idempotency_key=idempotency_key,
                decision=(
                    evaluation.decision.value
                    if isinstance(evaluation.decision, RiskDecision)
                    else str(evaluation.decision)
                ),
                reason_code=(
                    evaluation.reason_code.value
                    if isinstance(evaluation.reason_code, RiskReasonCode)
                    else str(evaluation.reason_code)
                ),
                approved_quantity=evaluation.approved_quantity,
                message=evaluation.message,
                checks=evaluation.checks,
                created_at=utc_now(),
            )
        )
        await self.session.commit()
        return rid

    async def record_order(self, order: Order) -> None:
        self.session.add(
            OrderORM(
                id=order.id,
                client_order_id=order.client_order_id,
                idempotency_key=order.idempotency_key,
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
                price=order.price,
                average_fill_price=order.average_fill_price,
                status=order.status.value,
                strategy_name=order.strategy_name,
                signal_id=order.signal_id,
                risk_decision=(
                    order.risk_decision.value if order.risk_decision else None
                ),
                risk_reason_code=(
                    order.risk_reason_code.value if order.risk_reason_code else None
                ),
                fees=order.fees,
                created_at=order.created_at,
                updated_at=order.updated_at,
                payload=order.metadata,
            )
        )
        await self.session.commit()

    async def record_fill(self, fill: Fill) -> None:
        self.session.add(
            FillORM(
                id=fill.id,
                order_id=fill.order_id,
                symbol=fill.symbol,
                side=fill.side.value,
                quantity=fill.quantity,
                price=fill.price,
                fee=fill.fee,
                timestamp=fill.timestamp,
            )
        )
        await self.session.commit()

    async def record_system_event(
        self,
        event_type: str,
        message: str,
        *,
        severity: str = "info",
        payload: dict | None = None,
    ) -> None:
        self.session.add(
            SystemEventORM(
                event_type=event_type,
                severity=severity,
                message=message,
                payload=payload or {},
                created_at=utc_now(),
            )
        )
        await self.session.commit()

    async def list_orders(self, *, limit: int = 500) -> list[Order]:
        from sqlalchemy import select

        from app.models.domain.enums import OrderSide, OrderStatus, OrderType

        rows = (
            (
                await self.session.execute(
                    select(OrderORM).order_by(OrderORM.created_at.desc()).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        out: list[Order] = []
        for row in reversed(list(rows)):
            out.append(
                Order(
                    id=row.id,
                    client_order_id=row.client_order_id,
                    idempotency_key=row.idempotency_key,
                    symbol=row.symbol,
                    side=OrderSide(row.side),
                    order_type=OrderType(row.order_type),
                    quantity=Decimal(str(row.quantity)),
                    filled_quantity=Decimal(str(row.filled_quantity or 0)),
                    price=Decimal(str(row.price)) if row.price is not None else None,
                    average_fill_price=(
                        Decimal(str(row.average_fill_price))
                        if row.average_fill_price is not None
                        else None
                    ),
                    status=OrderStatus(row.status),
                    strategy_name=row.strategy_name,
                    signal_id=row.signal_id,
                    fees=Decimal(str(row.fees or 0)),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    metadata=dict(row.payload or {}),
                )
            )
        return out

    async def list_fills(self, *, limit: int = 500) -> list[Fill]:
        from sqlalchemy import select

        from app.models.domain.enums import OrderSide

        rows = (
            (
                await self.session.execute(
                    select(FillORM).order_by(FillORM.timestamp.desc()).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        out: list[Fill] = []
        for row in reversed(list(rows)):
            out.append(
                Fill(
                    id=row.id,
                    order_id=row.order_id,
                    symbol=row.symbol,
                    side=OrderSide(row.side),
                    quantity=Decimal(str(row.quantity)),
                    price=Decimal(str(row.price)),
                    fee=Decimal(str(row.fee)),
                    timestamp=row.timestamp,
                )
            )
        return out
