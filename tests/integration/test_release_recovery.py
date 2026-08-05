"""Release recovery edge cases: partial fill, kill switch, halt, corrupt checkpoint."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.execution.paper.engine import PaperConfig, PaperTradingEngine
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
    is_reconciliation_healthy,
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


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )


@pytest.mark.asyncio
async def test_restart_after_partial_fill():
    engine, factory = await _db()
    session = get_paper_session()
    session.paper = PaperTradingEngine(
        PaperConfig(
            initial_cash=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            spread_rate=Decimal("0"),
            partial_fill_fraction=Decimal("0.5"),
        )
    )
    session.paper.set_mark_price("BTC/USDT", Decimal("100"))
    risk = RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("2"),
        message="ok",
    )
    order = await session.paper.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("2"),
            idempotency_key="partial-1",
        ),
        risk,
    )
    assert order.status.value == "PARTIALLY_FILLED"
    assert order.filled_quantity == Decimal("1")
    cash = session.paper.state.cash
    async with factory() as db:
        await persist_paper_session(db)
    reset_paper_session()
    async with factory() as db:
        await hydrate_paper_session_from_db(db)
    restored = get_paper_session()
    assert restored.paper.state.cash == cash
    assert "BTC/USDT" in restored.paper.state.positions
    assert restored.paper.state.positions["BTC/USDT"].quantity == Decimal("1")
    # Duplicate fill prevented via idempotency
    again = await restored.paper.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("2"),
            idempotency_key="partial-1",
        ),
        risk,
    )
    assert again.id == order.id
    await engine.dispose()


@pytest.mark.asyncio
async def test_restart_after_kill_switch_and_during_recon_halt():
    engine, factory = await _db()
    session = get_paper_session()
    session.kill_switch_enabled = True
    apply_halt_from_storage(halted=True)
    session.risk_engine.state.reconciliation_healthy = False
    async with factory() as db:
        await store.save_reconciliation_halt(db, halted=True, detail="test")
        await persist_paper_session(db)
    reset_paper_session()
    clear_reconciliation_halt()
    async with factory() as db:
        await hydrate_paper_session_from_db(db)
    restored = get_paper_session()
    assert restored.kill_switch_enabled is True
    assert is_reconciliation_healthy() is False
    await engine.dispose()


@pytest.mark.asyncio
async def test_corrupt_checkpoint_fails_closed_on_negative_cash_recon():
    engine, factory = await _db()
    session = get_paper_session()
    session.paper.state.cash = Decimal("100")
    async with factory() as db:
        await persist_paper_session(db)
        # Corrupt durable checkpoint cash
        await store.set_system_value(
            db,
            store.KEY_PAPER_CHECKPOINT,
            {
                "cash": "-999",
                "realized_pnl": "0",
                "peak_equity": "100",
                "daily_start_equity": "100",
                "consecutive_losses": 0,
                "idempotency_index": {},
                "positions": {},
                "fills": [],
                "orders": [],
            },
        )
    reset_paper_session()
    async with factory() as db:
        await hydrate_paper_session_from_db(db)
    assert get_paper_session().paper.state.cash == Decimal("-999")
    from app.services.reconciliation import run_paper_reconciliation

    result = await run_paper_reconciliation(persist=False)
    assert result.healthy is False
    assert is_reconciliation_healthy() is False
    await engine.dispose()


@pytest.mark.asyncio
async def test_repository_roundtrip():
    from app.repositories import (
        PaperAccountRepository,
        RiskStateRepository,
        StrategyStateRepository,
    )

    engine, factory = await _db()
    async with factory() as db:
        accounts = PaperAccountRepository(db)
        await accounts.upsert(
            cash=Decimal("1234"),
            realized_pnl=Decimal("10"),
            peak_equity=Decimal("1300"),
            daily_start_equity=Decimal("1200"),
            consecutive_losses=1,
            fees_paid=Decimal("0.5"),
            idempotency_index={"k": "v"},
        )
        risk = RiskStateRepository(db)
        await risk.upsert_from_session(
            circuit_breaker_open=False,
            circuit_breaker_reason="",
            seen_idempotency_keys={"a"},
            reconciliation_healthy=True,
            risk_engine_healthy=True,
            database_healthy=True,
            market_data_healthy=True,
            peak_equity=Decimal("1300"),
            daily_start_equity=Decimal("1200"),
            consecutive_losses=1,
            kill_switch_enabled=False,
        )
        strat = StrategyStateRepository(db)
        await strat.upsert(
            selected_strategy_id="ema_crossover",
            running_strategies=["ema_crossover"],
            param_overrides={},
        )
        assert (await accounts.get())["cash"] == Decimal("1234")
        assert (await risk.get())["consecutive_losses"] == 1
        assert (await strat.get())["selected_strategy_id"] == "ema_crossover"
    await engine.dispose()
