"""ORM models for paper performance analytics."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClosedTradeORM(Base):
    """Round-trip paper trade (entry → exit) for the performance journal."""

    __tablename__ = "closed_trades"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))  # long exit recorded as sell
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    exit_price: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    quantity: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    fees: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    slippage: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    net_pnl: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    roi_pct: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    duration_seconds: Mapped[int] = mapped_column(Integer)
    exit_reason: Mapped[str] = mapped_column(String(64))
    risk_score: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    market_regime: Mapped[str] = mapped_column(String(32))
    paper_session_id: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fill_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PerformanceReportORM(Base):
    """Cached daily / weekly / monthly performance report."""

    __tablename__ = "performance_reports"
    __table_args__ = (
        UniqueConstraint(
            "period", "period_start", "period_end", name="uq_performance_reports_period"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    period: Mapped[str] = mapped_column(String(16), index=True)  # daily|weekly|monthly
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
