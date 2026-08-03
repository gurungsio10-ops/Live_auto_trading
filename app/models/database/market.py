"""ORM models for market data: symbols and candles."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SymbolORM(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    base: Mapped[str] = mapped_column(String(16), nullable=False)
    quote: Mapped[str] = mapped_column(String(16), nullable=False)
    price_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    quantity_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    min_notional: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    step_size: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CandleORM(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "open_time", name="uq_candle_key"),
        Index("ix_candles_symbol_tf_time", "symbol", "timeframe", "open_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    open: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(36, 18), nullable=False)
    quote_volume: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    trade_count: Mapped[int | None] = mapped_column(Integer)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
