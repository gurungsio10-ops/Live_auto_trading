"""Restart recovery: kill switch + cycle idempotency survive hydrate."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.services import paper_cycle
from app.services import paper_persistence as store
from app.services.paper_session import (
    get_paper_session,
    hydrate_paper_session_from_db,
    persist_paper_session,
    reset_paper_session,
)
from app.services.sample_market import build_ema_crossover_candles


@pytest.fixture(autouse=True)
def _reset():
    reset_paper_session()
    paper_cycle.reset_cycle_state()
    yield
    reset_paper_session()
    paper_cycle.reset_cycle_state()


@pytest.mark.asyncio
async def test_kill_switch_and_portfolio_survive_restart():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    session = get_paper_session()
    session.kill_switch_enabled = True
    session.paper.state.cash = Decimal("9000")
    async with factory() as db:
        await persist_paper_session(db)

    reset_paper_session()
    paper_cycle.reset_cycle_state()
    assert get_paper_session().kill_switch_enabled is False

    async with factory() as db:
        await hydrate_paper_session_from_db(db)

    restored = get_paper_session()
    assert restored.kill_switch_enabled is True
    assert restored.paper.state.cash == Decimal("9000")
    await engine.dispose()


@pytest.mark.asyncio
async def test_cycle_idempotent_across_restart():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    settings = Settings(trading_mode="paper", kill_switch_enabled=False, _env_file=None)
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    source = paper_cycle.ProvidedCandleSource(candles=candles)

    session = get_paper_session()
    orch = paper_cycle.get_or_create_orchestrator(
        settings=settings, paper_engine=session.paper
    )
    first = await paper_cycle.run_paper_trading_cycle(
        settings=settings,
        candle_source=source,
        orchestrator=orch,
    )
    assert first.accepted is True
    assert first.idempotent_replay is False
    assert first.order_status == "FILLED"

    async with factory() as db:
        await store.save_cycle_keys(db, paper_cycle.export_processed_cycle_keys())
        await persist_paper_session(db, correlation_id=first.correlation_id)

    reset_paper_session()
    paper_cycle.reset_cycle_state()
    async with factory() as db:
        await hydrate_paper_session_from_db(db)
        loaded = await paper_cycle.load_persisted_cycle_keys(db)
        paper_cycle.set_processed_cycle_keys(loaded)

    restored = get_paper_session()
    orch2 = paper_cycle.get_or_create_orchestrator(
        settings=settings, paper_engine=restored.paper
    )
    second = await paper_cycle.run_paper_trading_cycle(
        settings=settings,
        candle_source=source,
        orchestrator=orch2,
    )
    assert second.idempotent_replay is True
    # Positions restored from checkpoint; fills list is process-local and may be empty.
    assert "BTC/USDT" in restored.paper.state.positions
    assert restored.paper.state.cash < Decimal("10000")
    await engine.dispose()
