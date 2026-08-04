"""Consolidation tests: cycle locks, trading_enabled SSOT, recon halt."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time import utc_now
from app.db.base import Base, create_engine
from app.services import paper_cycle
from app.services.cycle_lock import (
    LockStatus,
    acquire_cycle_lock,
    make_cycle_lock_key,
    release_cycle_lock,
)
from app.services.paper_session import get_paper_session, reset_paper_session
from app.services.reconciliation import (
    clear_reconciliation_halt,
    is_reconciliation_healthy,
    run_paper_reconciliation,
)
from app.services.trading_scheduler import scheduler_status


@pytest.fixture(autouse=True)
def _reset():
    paper_cycle.reset_cycle_state()
    reset_paper_session()
    clear_reconciliation_halt()
    yield
    paper_cycle.reset_cycle_state()
    reset_paper_session()
    clear_reconciliation_halt()


@pytest.mark.asyncio
async def test_cycle_lock_acquire_and_hold():
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    key = make_cycle_lock_key(
        account_id="paper-default",
        strategy_id="ema_crossover",
        strategy_version="1.0.0",
        symbol="BTC/USDT",
        timeframe="1m",
        candle_open_time=utc_now(),
    )
    async with factory() as session:
        first = await acquire_cycle_lock(session, lock_key=key, ttl_seconds=60)
        assert first.status == LockStatus.ACQUIRED
        assert first.lock is not None
    async with factory() as session:
        second = await acquire_cycle_lock(session, lock_key=key, ttl_seconds=60)
        assert second.status == LockStatus.HELD
    async with factory() as session:
        await release_cycle_lock(
            session, lock_key=key, owner=first.lock.owner  # type: ignore[union-attr]
        )
        third = await acquire_cycle_lock(session, lock_key=key, ttl_seconds=60)
        assert third.status == LockStatus.ACQUIRED
    await engine.dispose()


@pytest.mark.asyncio
async def test_trading_enabled_lives_on_paper_session():
    session = reset_paper_session()
    assert session.trading_enabled is False or isinstance(session.trading_enabled, bool)
    session.set_trading_enabled(True)
    assert get_paper_session().trading_enabled is True
    from app.api import mvp as mvp_api

    assert mvp_api._trading_enabled() is True
    session.set_trading_enabled(False)
    assert mvp_api._trading_enabled() is False


@pytest.mark.asyncio
async def test_idempotent_cycle_no_duplicate_orders():
    reset_paper_session()
    first = await paper_cycle.run_paper_trading_cycle(
        symbol="BTC/USDT", timeframe="1m", strategy_id="ema_crossover"
    )
    second = await paper_cycle.run_paper_trading_cycle(
        symbol="BTC/USDT", timeframe="1m", strategy_id="ema_crossover"
    )
    assert second.idempotent_replay is True
    assert second.order_id is None or second.order_id == first.order_id


@pytest.mark.asyncio
async def test_reconciliation_halt_blocks_cycle():
    session = reset_paper_session()
    session.paper.state.cash = Decimal("-5")
    result = await run_paper_reconciliation(persist=False)
    assert result.healthy is False
    assert is_reconciliation_healthy() is False
    cycle = await paper_cycle.run_paper_trading_cycle(
        symbol="BTC/USDT", timeframe="1m", strategy_id="ema_crossover"
    )
    assert cycle.reject_reason == "RECONCILIATION_HALT"
    clear_reconciliation_halt()


def test_scheduler_status_fields():
    status = scheduler_status()
    assert "consecutive_failures" in status
    assert "paused_by_failures" in status
    assert "heartbeat_at" in status


@pytest.mark.asyncio
async def test_expired_lock_can_be_reacquired():
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    key = "test:expired"
    async with factory() as session:
        first = await acquire_cycle_lock(session, lock_key=key, ttl_seconds=1)
        assert first.status == LockStatus.ACQUIRED
        # Force expiry
        from app.services.cycle_lock import CycleLockORM

        row = await session.get(CycleLockORM, key)
        assert row is not None
        row.expires_at = utc_now() - timedelta(seconds=5)
        await session.commit()
    async with factory() as session:
        again = await acquire_cycle_lock(session, lock_key=key, ttl_seconds=30)
        assert again.status == LockStatus.ACQUIRED
    await engine.dispose()
