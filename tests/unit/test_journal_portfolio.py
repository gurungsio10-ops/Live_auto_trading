"""Phase 9: journal + portfolio persistence."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.time import utc_now
from app.journal.store import (
    FillORM,
    JournalStore,
    OrderORM,
    RiskDecisionORM,
    SignalORM,
    SystemEventORM,
)
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
    SignalDirection,
)
from app.models.domain.trading import (
    Fill,
    Order,
    PortfolioState,
    Position,
    RiskEvaluation,
    TradeSignal,
)
from app.portfolio.service import PortfolioService


@pytest.mark.asyncio
async def test_journal_records_signal_and_rejection(db_session):
    store = JournalStore(db_session)
    signal = TradeSignal(
        strategy_name="EMA Trend Strategy",
        strategy_version="1.0.0",
        symbol="BTC/USDT",
        direction=SignalDirection.BUY,
        confidence=Decimal("0.7"),
        entry_rationale="test",
        invalidation_condition="stop",
        input_data_fingerprint="fp1",
    )
    sid = await store.record_signal(signal)
    assert sid

    evaluation = RiskEvaluation(
        decision=RiskDecision.REJECTED,
        reason_code=RiskReasonCode.DAILY_LOSS_LIMIT_REACHED,
        message="rejected",
    )
    rid = await store.record_risk_decision(idempotency_key="k1", evaluation=evaluation)
    assert rid

    signals = (await db_session.scalars(select(SignalORM))).all()
    decisions = (await db_session.scalars(select(RiskDecisionORM))).all()
    assert len(signals) == 1
    assert len(decisions) == 1
    assert decisions[0].reason_code == "DAILY_LOSS_LIMIT_REACHED"
    assert decisions[0].decision == "REJECTED"
    assert decisions[0].approved_quantity is None

    order = Order(
        id="o1",
        client_order_id="c1",
        idempotency_key="k1",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        status=OrderStatus.REJECTED,
        risk_decision=RiskDecision.REJECTED,
        risk_reason_code=RiskReasonCode.DAILY_LOSS_LIMIT_REACHED,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    await store.record_order(order)
    await store.record_fill(
        Fill(
            id="f1",
            order_id="o1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("100"),
            fee=Decimal("0.1"),
        )
    )
    await store.record_system_event("TEST", "hello", severity="warn", payload={"k": 1})

    orders = (await db_session.scalars(select(OrderORM))).all()
    fills = (await db_session.scalars(select(FillORM))).all()
    events = (await db_session.scalars(select(SystemEventORM))).all()
    assert len(orders) == 1
    assert orders[0].risk_reason_code == "DAILY_LOSS_LIMIT_REACHED"
    assert orders[0].status == "REJECTED"
    assert len(fills) == 1
    assert fills[0].fee.quantize(Decimal("0.0001")) == Decimal("0.1000")
    assert len(events) == 1
    assert events[0].severity == "warn"
    assert events[0].payload == {"k": 1}


@pytest.mark.asyncio
async def test_journal_records_approved_risk_decision(db_session):
    store = JournalStore(db_session)
    rid = await store.record_risk_decision(
        idempotency_key="ok-1",
        evaluation=RiskEvaluation(
            decision=RiskDecision.APPROVED,
            reason_code=RiskReasonCode.OK,
            approved_quantity=Decimal("0.01"),
            message="OK",
            checks={"live_gating": "n/a"},
        ),
    )
    row = await db_session.scalar(
        select(RiskDecisionORM).where(RiskDecisionORM.id == rid)
    )
    assert row is not None
    assert row.decision == "APPROVED"
    assert row.reason_code == "OK"
    assert row.approved_quantity == Decimal("0.01")


def test_portfolio_snapshot():
    svc = PortfolioService(
        cash=Decimal("9000"),
        positions=[
            Position(
                symbol="BTC/USDT",
                quantity=Decimal("0.01"),
                entry_price=Decimal("100000"),
                current_price=Decimal("110000"),
                unrealized_pnl=Decimal("100"),
                opened_at=utc_now(),
            )
        ],
        realized_pnl=Decimal("50"),
    )
    snap = svc.snapshot()
    assert isinstance(snap, PortfolioState)
    assert snap.equity == Decimal("9000") + Decimal("0.01") * Decimal("110000")
    assert snap.unrealized_pnl == Decimal("100")
    assert snap.realized_pnl == Decimal("50")
    assert snap.peak_equity == snap.equity
    assert snap.drawdown == Decimal("0")
    assert len(snap.open_positions) == 1


def test_portfolio_drawdown_after_peak():
    svc = PortfolioService(cash=Decimal("10000"))
    first = svc.snapshot()
    assert first.peak_equity == Decimal("10000")
    svc.cash = Decimal("8000")
    second = svc.snapshot()
    assert second.peak_equity == Decimal("10000")
    assert second.drawdown == Decimal("0.2")
    assert isinstance(second.equity, Decimal)


@pytest.mark.asyncio
async def test_journal_persists_on_postgres():
    """Smoke: write rejected decision into live Postgres Phase 9 tables."""
    engine = create_async_engine(
        "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas"
    )
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with Session() as session:
            store = JournalStore(session)
            rid = await store.record_risk_decision(
                idempotency_key=f"pg-reject-{utc_now().timestamp()}",
                evaluation=RiskEvaluation(
                    decision=RiskDecision.REJECTED,
                    reason_code=RiskReasonCode.KILL_SWITCH_ACTIVE,
                    message="postgres smoke",
                ),
            )
            row = await session.scalar(
                select(RiskDecisionORM).where(RiskDecisionORM.id == rid)
            )
            assert row is not None
            assert row.reason_code == "KILL_SWITCH_ACTIVE"
            assert row.decision == "REJECTED"
    finally:
        await engine.dispose()
