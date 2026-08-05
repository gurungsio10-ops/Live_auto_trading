"""Durable recovery: risk/strategy/daily equity/recon halt survive restart."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.domain.enums import OrderSide, OrderType, RiskDecision, RiskReasonCode
from app.models.domain.trading import OrderRequest, RiskEvaluation
from app.services import paper_cycle
from app.services import paper_persistence as store
from app.services.paper_session import (
    get_paper_session,
    hydrate_paper_session_from_db,
    persist_paper_session,
    reset_paper_session,
)
from app.services.reconciliation import (
    apply_halt_from_storage,
    clear_reconciliation_halt,
    clear_reconciliation_halt_persisted,
    is_reconciliation_healthy,
    reconciliation_status,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_paper_session()
    paper_cycle.reset_cycle_state()
    clear_reconciliation_halt()
    yield
    reset_paper_session()
    paper_cycle.reset_cycle_state()
    clear_reconciliation_halt()


async def _memory_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, factory


@pytest.mark.asyncio
async def test_daily_equity_and_risk_state_survive_restart():
    engine, factory = await _memory_db()
    session = get_paper_session()
    session._daily_start_equity = Decimal("9500")
    session._peak_equity = Decimal("11000")
    session._consecutive_losses = 3
    session.paper.state.cash = Decimal("8800")
    session.risk_engine.state.circuit_breaker_open = True
    session.risk_engine.state.circuit_breaker_reason = "test_trip"
    session.risk_engine.state.seen_idempotency_keys.add("idemp-a")
    session.selected_strategy_id = "rsi_mean_reversion"
    session.running_strategies.add("rsi_mean_reversion")
    session.param_overrides = {"rsi_mean_reversion": {"period": 14}}

    async with factory() as db:
        await persist_paper_session(db)

    reset_paper_session()
    paper_cycle.reset_cycle_state()
    restored_before = get_paper_session()
    assert restored_before._daily_start_equity != Decimal("9500")

    async with factory() as db:
        await hydrate_paper_session_from_db(db)
        account = await store.load_paper_account(db)
        risk = await store.load_risk_state(db)
        strategy = await store.load_strategy_state(db)

    restored = get_paper_session()
    assert restored._daily_start_equity == Decimal("9500")
    assert restored._peak_equity == Decimal("11000")
    assert restored._consecutive_losses == 3
    assert restored.paper.state.cash == Decimal("8800")
    assert restored.risk_engine.state.circuit_breaker_open is True
    assert "idemp-a" in restored.risk_engine.state.seen_idempotency_keys
    assert restored.selected_strategy_id == "rsi_mean_reversion"
    assert "rsi_mean_reversion" in restored.running_strategies
    assert account is not None
    assert risk is not None
    assert strategy is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_reconciliation_halt_survives_restart_and_clear_persists():
    engine, factory = await _memory_db()
    apply_halt_from_storage(halted=True)
    get_paper_session().risk_engine.state.reconciliation_healthy = False

    async with factory() as db:
        await store.save_reconciliation_halt(db, halted=True, detail="cash_mismatch")
        await persist_paper_session(db)

    reset_paper_session()
    clear_reconciliation_halt()
    assert is_reconciliation_healthy() is True

    async with factory() as db:
        await hydrate_paper_session_from_db(db)

    assert is_reconciliation_healthy() is False
    assert get_paper_session().risk_engine.state.reconciliation_healthy is False
    assert reconciliation_status()["halted"] is True

    # Persist clear so a second hydrate stays healthy.
    async with factory() as db:
        # Use direct store clear path with this test DB (shared engine may differ).
        clear_reconciliation_halt()
        await store.save_reconciliation_halt(db, halted=False, detail="cleared")

    reset_paper_session()
    async with factory() as db:
        await hydrate_paper_session_from_db(db)
    assert is_reconciliation_healthy() is True
    await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_fill_prevention_via_idempotency_after_restart():
    engine, factory = await _memory_db()
    session = get_paper_session()
    session.paper.set_mark_price("BTC/USDT", Decimal("50000"))
    risk = RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("0.01"),
        message="ok",
    )
    req = OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        strategy_name="test",
        idempotency_key="dup-key-1",
    )
    first = await session.paper.submit(req, risk)
    assert first.status.value == "FILLED"
    cash_after = session.paper.state.cash
    fills_after = len(session.paper.state.fills)

    async with factory() as db:
        await persist_paper_session(db)

    reset_paper_session()
    async with factory() as db:
        await hydrate_paper_session_from_db(db)

    restored = get_paper_session()
    restored.paper.set_mark_price("BTC/USDT", Decimal("50000"))
    second = await restored.paper.submit(req, risk)
    assert second.id == first.id
    assert restored.paper.state.cash == cash_after
    assert len(restored.paper.state.fills) == fills_after
    await engine.dispose()


@pytest.mark.asyncio
async def test_processed_cycle_keys_dual_write_table():
    engine, factory = await _memory_db()
    keys = {("BTC/USDT", "1.0.0", "1m", "2026-08-04T00:00:00+00:00")}
    async with factory() as db:
        await store.save_cycle_keys(db, keys)
        loaded = await store.load_cycle_keys(db)
        # Wipe system_state key and ensure normalized table still loads.
        await store.set_system_value(db, store.KEY_CYCLE_KEYS, {})
        # Empty keys list → fallback to processed_cycle_keys table
        await store.set_system_value(db, store.KEY_CYCLE_KEYS, {"keys": []})
        # Direct table load via empty system_state
        from sqlalchemy import delete

        from app.models.database.portfolio import SystemStateORM

        await db.execute(
            delete(SystemStateORM).where(SystemStateORM.key == store.KEY_CYCLE_KEYS)
        )
        await db.commit()
        loaded2 = await store.load_cycle_keys(db)

    assert loaded == keys
    assert loaded2 == keys
    await engine.dispose()


@pytest.mark.asyncio
async def test_clear_reconciliation_halt_persisted_helper():
    """Helper clears memory; with shared engine unavailable still clears memory."""
    apply_halt_from_storage(halted=True)
    get_paper_session().risk_engine.state.reconciliation_healthy = False
    await clear_reconciliation_halt_persisted()
    assert is_reconciliation_healthy() is True
