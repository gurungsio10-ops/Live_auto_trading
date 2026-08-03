"""Phase 9: journal + portfolio persistence."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.journal.store import JournalStore, RiskDecisionORM, SignalORM
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
    await store.record_system_event("TEST", "hello")


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
