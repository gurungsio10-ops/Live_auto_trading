"""ORM models for portfolio / strategy-run / journal persistence (paper slice)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StrategyRunORM(Base):
    __tablename__ = "strategy_runs"
    __table_args__ = (
        UniqueConstraint(
            "strategy_name",
            "strategy_version",
            "symbol",
            "timeframe",
            "candle_open_time",
            name="uq_strategy_run_candle",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(128))
    strategy_version: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(16))
    candle_open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str] = mapped_column(String(64))
    direction: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BalanceORM(Base):
    __tablename__ = "balances"
    __table_args__ = (UniqueConstraint("asset", name="uq_balances_asset"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset: Mapped[str] = mapped_column(String(32))
    free: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    locked: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=0)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PositionORM(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("symbol", name="uq_positions_symbol"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    entry_price: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    current_price: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    strategy_name: Mapped[str | None] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PortfolioSnapshotORM(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    equity: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    daily_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    peak_equity: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    drawdown: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    fees_paid: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    exposure: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TradeJournalORM(Base):
    __tablename__ = "trade_journal"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    strategy_run_id: Mapped[str | None] = mapped_column(String(64))
    order_id: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SystemStateORM(Base):
    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
