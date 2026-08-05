"""Merge-prep verification: durable state, risk gate, admin clear-halt, migrations."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["ADMIN_API_TOKEN"] = "test-admin-token"
os.environ.setdefault("TRADING_MODE", "paper")

from app.core.config import get_settings
from app.db.base import Base
from app.execution.gateway import OrderGateway, RiskBlockedError
from app.main import app
from app.models.domain.enums import OrderSide, OrderType, RiskDecision, RiskReasonCode
from app.models.domain.trading import OrderRequest, PortfolioState, RiskEvaluation
from app.risk.engine import RiskContext
from app.services import paper_cycle
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
    run_paper_reconciliation,
)


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    os.environ["ADMIN_API_TOKEN"] = "test-admin-token"
    get_settings.cache_clear()
    reset_paper_session()
    paper_cycle.reset_cycle_state()
    clear_reconciliation_halt()
    yield
    reset_paper_session()
    paper_cycle.reset_cycle_state()
    clear_reconciliation_halt()
    get_settings.cache_clear()


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, factory


@pytest.mark.asyncio
async def test_full_durable_state_survives_restart():
    engine, factory = await _db()
    session = get_paper_session()
    session.kill_switch_enabled = True
    session._daily_start_equity = Decimal("9700")
    session._peak_equity = Decimal("10500")
    session._consecutive_losses = 2
    session.paper.state.cash = Decimal("8500")
    session.paper.state.realized_pnl = Decimal("125.50")
    session.paper.set_mark_price("ETH/USDT", Decimal("2000"))
    # Seed a position with WAC entry
    from app.core.time import utc_now
    from app.models.domain.trading import Position

    session.paper.state.positions["ETH/USDT"] = Position(
        symbol="ETH/USDT",
        quantity=Decimal("1.5"),
        entry_price=Decimal("1950.25"),
        current_price=Decimal("2000"),
        unrealized_pnl=Decimal("74.625"),
        opened_at=utc_now(),
        strategy_name="ema_crossover",
    )
    session.risk_engine.state.seen_idempotency_keys.add("k1")
    session.risk_engine.state.circuit_breaker_open = False
    session.selected_strategy_id = "breakout"
    session.running_strategies = {"breakout"}
    session.param_overrides = {"breakout": {"lookback": 20}}

    async with factory() as db:
        await persist_paper_session(db)

    reset_paper_session()
    async with factory() as db:
        await hydrate_paper_session_from_db(db)

    restored = get_paper_session()
    assert restored.kill_switch_enabled is True
    assert restored.paper.state.cash == Decimal("8500")
    assert restored.paper.state.realized_pnl == Decimal("125.50")
    pos = restored.paper.state.positions["ETH/USDT"]
    assert pos.quantity == Decimal("1.5")
    assert pos.entry_price == Decimal("1950.25")
    assert restored._daily_start_equity == Decimal("9700")
    assert restored._peak_equity == Decimal("10500")
    assert restored._consecutive_losses == 2
    assert "k1" in restored.risk_engine.state.seen_idempotency_keys
    assert restored.selected_strategy_id == "breakout"
    assert restored.running_strategies == {"breakout"}
    await engine.dispose()


@pytest.mark.asyncio
async def test_recon_halt_blocks_cycle_and_clear_requires_admin():
    apply_halt_from_storage(halted=True)
    get_paper_session().risk_engine.state.reconciliation_healthy = False
    assert is_reconciliation_healthy() is False

    settings = get_settings()
    result = await paper_cycle.run_paper_trading_cycle(settings=settings)
    assert result.reject_reason == "RECONCILIATION_HALT"
    assert result.accepted is False

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.post("/api/v1/reconciliation/clear-halt")
        assert denied.status_code in {401, 403, 503}
        ok = await client.post(
            "/api/v1/reconciliation/clear-halt",
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert ok.status_code == 200
        assert ok.json()["ok"] is True
    assert is_reconciliation_healthy() is True


@pytest.mark.asyncio
async def test_order_gateway_never_bypasses_risk_engine():
    session = get_paper_session()
    session.kill_switch_enabled = True
    gateway = OrderGateway(session.paper, session.risk_engine)
    session.paper.set_mark_price("BTC/USDT", Decimal("50000"))
    req = OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        idempotency_key="risk-bypass-1",
    )
    ctx = RiskContext(
        portfolio=PortfolioState(
            cash_balance=session.paper.state.cash,
            equity=session.paper.state.cash,
            open_positions=[],
            peak_equity=session.paper.state.cash,
            daily_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
        ),
        mark_price=Decimal("50000"),
        kill_switch_enabled=True,
        trading_mode="paper",
    )
    with pytest.raises(RiskBlockedError) as exc:
        await gateway.submit(req, ctx)
    assert exc.value.evaluation.decision == RiskDecision.HALTED
    assert exc.value.evaluation.reason_code == RiskReasonCode.KILL_SWITCH_ACTIVE
    assert len(session.paper.state.orders) == 0


@pytest.mark.asyncio
async def test_duplicate_fill_idempotency_and_negative_cash_halts():
    engine, _factory = await _db()
    session = get_paper_session()
    session.paper.set_mark_price("BTC/USDT", Decimal("100"))
    risk = RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("1"),
        message="ok",
    )
    req = OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        idempotency_key="fill-once",
    )
    first = await session.paper.submit(req, risk)
    fills = len(session.paper.state.fills)
    cash = session.paper.state.cash
    second = await session.paper.submit(req, risk)
    assert second.id == first.id
    assert len(session.paper.state.fills) == fills
    assert session.paper.state.cash == cash

    # Corrupt cash → recon must halt
    session.paper.state.cash = Decimal("-1")
    result = await run_paper_reconciliation(persist=False)
    assert result.healthy is False
    assert is_reconciliation_healthy() is False
    await engine.dispose()


def test_alembic_chain_files_present():
    versions = Path("alembic/versions")
    names = sorted(p.name for p in versions.glob("000*.py"))
    assert names == [
        "0001_phase2_symbols_candles.py",
        "0002_phase9_journal.py",
        "0003_users.py",
        "0004_paper_slice_persistence.py",
        "0005_cycle_locks_scheduler_recon.py",
        "0006_paper_account_risk_strategy_state.py",
        "0007_performance_analytics.py",
    ]


@pytest.mark.asyncio
async def test_persist_failure_fail_closed_helper():
    paper_cycle._fail_closed_persistence(reason="unit-test")
    session = get_paper_session()
    assert session.trading_paused is True
    assert session.risk_engine.state.database_healthy is False
    assert session.risk_engine.state.reconciliation_healthy is False
    assert is_reconciliation_healthy() is False
