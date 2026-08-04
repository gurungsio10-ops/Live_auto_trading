"""Database-backed cycle lock — final uniqueness protection for paper cycles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import ensure_utc, utc_now
from app.db.base import Base


class CycleLockORM(Base):
    __tablename__ = "cycle_locks"

    lock_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    owner: Mapped[str] = mapped_column(String(64))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SchedulerRunORM(Base):
    __tablename__ = "scheduler_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="running")
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(16))
    strategy_id: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)


class ReconciliationReportORM(Base):
    __tablename__ = "reconciliation_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    healthy: Mapped[str] = mapped_column(String(8))  # "true"/"false" for sqlite ease
    detail: Mapped[str] = mapped_column(String(512))
    cash: Mapped[str] = mapped_column(String(64))
    position_count: Mapped[str] = mapped_column(String(32))
    payload: Mapped[str] = mapped_column(String(4096), default="{}")


@dataclass(frozen=True, slots=True)
class CycleLock:
    lock_key: str
    owner: str
    correlation_id: str | None


class LockStatus(str, Enum):
    ACQUIRED = "acquired"
    HELD = "held"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class LockAcquireResult:
    status: LockStatus
    lock: CycleLock | None = None


def make_cycle_lock_key(
    *,
    account_id: str,
    strategy_id: str,
    strategy_version: str,
    symbol: str,
    timeframe: str,
    candle_open_time: datetime,
) -> str:
    ts = ensure_utc(candle_open_time).isoformat()
    return f"{account_id}:{strategy_id}:{strategy_version}:{symbol}:{timeframe}:{ts}"


async def acquire_cycle_lock(
    session: AsyncSession,
    *,
    lock_key: str,
    ttl_seconds: int = 120,
    correlation_id: str | None = None,
) -> LockAcquireResult:
    """Try to acquire a lock. Distinguishes held vs DB unavailable."""
    try:
        now = utc_now()
        existing = await session.get(CycleLockORM, lock_key)
        if existing is not None:
            if ensure_utc(existing.expires_at) > now:
                return LockAcquireResult(status=LockStatus.HELD)
            await session.delete(existing)
            await session.flush()

        owner = uuid4().hex
        row = CycleLockORM(
            lock_key=lock_key,
            owner=owner,
            acquired_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            correlation_id=correlation_id,
        )
        session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return LockAcquireResult(status=LockStatus.HELD)
        return LockAcquireResult(
            status=LockStatus.ACQUIRED,
            lock=CycleLock(
                lock_key=lock_key, owner=owner, correlation_id=correlation_id
            ),
        )
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
        return LockAcquireResult(status=LockStatus.UNAVAILABLE)


async def release_cycle_lock(
    session: AsyncSession, *, lock_key: str, owner: str
) -> None:
    try:
        row = await session.get(CycleLockORM, lock_key)
        if row is not None and row.owner == owner:
            await session.delete(row)
            await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass


async def record_scheduler_run(
    session: AsyncSession,
    *,
    run_id: str,
    symbol: str,
    timeframe: str,
    strategy_id: str,
    status: str,
    correlation_id: str | None = None,
    error: str | None = None,
    started_at: datetime | None = None,
) -> None:
    now = utc_now()
    row = await session.get(SchedulerRunORM, run_id)
    if row is None:
        session.add(
            SchedulerRunORM(
                id=run_id,
                started_at=started_at or now,
                finished_at=now if status != "running" else None,
                status=status,
                symbol=symbol,
                timeframe=timeframe,
                strategy_id=strategy_id,
                correlation_id=correlation_id,
                error=error,
            )
        )
    else:
        row.status = status
        row.finished_at = now
        row.error = error
        row.correlation_id = correlation_id
    await session.commit()


async def recent_scheduler_runs(
    session: AsyncSession, *, limit: int = 20
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(SchedulerRunORM)
            .order_by(SchedulerRunORM.started_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "strategy_id": r.strategy_id,
            "correlation_id": r.correlation_id,
            "error": r.error,
        }
        for r in rows
    ]


async def save_reconciliation_report(
    session: AsyncSession,
    *,
    healthy: bool,
    detail: str,
    cash: str,
    position_count: int,
    payload: dict[str, Any] | None = None,
) -> str:
    import json

    report_id = uuid4().hex
    session.add(
        ReconciliationReportORM(
            id=report_id,
            created_at=utc_now(),
            healthy="true" if healthy else "false",
            detail=detail[:512],
            cash=cash,
            position_count=str(position_count),
            payload=json.dumps(payload or {})[:4096],
        )
    )
    await session.commit()
    return report_id
