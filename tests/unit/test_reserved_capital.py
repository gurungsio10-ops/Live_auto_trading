"""Reserved capital / buying-power accounting for paper BUY orders."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.accounting.invariants import check_cycle_invariants
from app.execution.paper import PaperConfig, PaperTradingEngine
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.trading import OrderRequest, RiskEvaluation


def _risk_ok(qty: Decimal = Decimal("0.01")) -> RiskEvaluation:
    return RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=qty,
        message="OK",
    )


def _req(**overrides) -> OrderRequest:
    data = dict(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        idempotency_key=uuid4().hex,
    )
    data.update(overrides)
    return OrderRequest(**data)


@pytest.mark.asyncio
async def test_resting_limit_buy_reserves_capital():
    engine = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    order = await engine.submit(
        _req(
            order_type=OrderType.LIMIT,
            price=Decimal("90000"),
            quantity=Decimal("0.01"),
        ),
        _risk_ok(),
    )
    assert order.status == OrderStatus.SUBMITTED
    assert engine.state.reserved_cash == Decimal("900")
    assert engine.state.cash == Decimal("9100")
    assert engine.state.total_cash == Decimal("10000")
    assert order.metadata.get("reservation_open") == "true"
    report = check_cycle_invariants(
        cash=engine.state.cash,
        reserved_cash=engine.state.reserved_cash,
        positions=dict(engine.state.positions),
        realized_pnl=engine.state.realized_pnl,
        fills=list(engine.state.fills),
        orders=dict(engine.state.orders),
    )
    assert report.ok
    assert report.equity == Decimal("10000")


@pytest.mark.asyncio
async def test_cancel_releases_reservation_exactly_once():
    engine = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    order = await engine.submit(
        _req(
            order_type=OrderType.LIMIT,
            price=Decimal("90000"),
            quantity=Decimal("0.01"),
        ),
        _risk_ok(),
    )
    cancelled = await engine.cancel(order.id)
    assert cancelled.status == OrderStatus.CANCELLED
    assert engine.state.reserved_cash == Decimal("0")
    assert engine.state.cash == Decimal("10000")
    # Duplicate cancel must not double-credit.
    again = await engine.cancel(order.id)
    assert again.status == OrderStatus.CANCELLED
    assert engine.state.cash == Decimal("10000")
    assert engine.state.reserved_cash == Decimal("0")
    # Explicit second release is a no-op.
    engine._release_buy_reservation(engine.state.orders[order.id])
    assert engine.state.cash == Decimal("10000")


@pytest.mark.asyncio
async def test_expire_releases_reservation():
    engine = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    order = await engine.submit(
        _req(
            order_type=OrderType.LIMIT,
            price=Decimal("90000"),
            quantity=Decimal("0.01"),
        ),
        _risk_ok(),
    )
    expired = await engine.expire(order.id)
    assert expired.status == OrderStatus.EXPIRED
    assert engine.state.reserved_cash == Decimal("0")
    assert engine.state.cash == Decimal("10000")


@pytest.mark.asyncio
async def test_market_buy_fill_clears_reservation():
    engine = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    order = await engine.submit(_req(quantity=Decimal("0.01")), _risk_ok())
    assert order.status == OrderStatus.FILLED
    assert engine.state.reserved_cash == Decimal("0")
    assert order.metadata.get("reservation_open") == "false"
    assert engine.state.cash < Decimal("10000")
    report = check_cycle_invariants(
        cash=engine.state.cash,
        reserved_cash=engine.state.reserved_cash,
        positions=dict(engine.state.positions),
        realized_pnl=engine.state.realized_pnl,
        fills=list(engine.state.fills),
        orders=dict(engine.state.orders),
    )
    assert report.ok


@pytest.mark.asyncio
async def test_partial_fill_releases_proportional_reservation():
    engine = PaperTradingEngine(
        PaperConfig(
            initial_cash=Decimal("10000"),
            partial_fill_fraction=Decimal("0.5"),
        )
    )
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    order = await engine.submit(
        _req(quantity=Decimal("0.02")), _risk_ok(Decimal("0.02"))
    )
    assert order.status == OrderStatus.PARTIALLY_FILLED
    # Reserved half of 0.02 * 100000 = 2000 → 1000 remaining.
    assert engine.state.reserved_cash == Decimal("1000")
    assert order.metadata.get("reservation_open") == "true"
    report = check_cycle_invariants(
        cash=engine.state.cash,
        reserved_cash=engine.state.reserved_cash,
        positions=dict(engine.state.positions),
        realized_pnl=engine.state.realized_pnl,
        fills=list(engine.state.fills),
        orders=dict(engine.state.orders),
    )
    assert report.ok


@pytest.mark.asyncio
async def test_second_buy_cannot_over_allocate_available_cash():
    engine = PaperTradingEngine(PaperConfig(initial_cash=Decimal("1000")))
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    first = await engine.submit(
        _req(
            order_type=OrderType.LIMIT,
            price=Decimal("90000"),
            quantity=Decimal("0.01"),
            idempotency_key="first",
        ),
        _risk_ok(),
    )
    assert first.status == OrderStatus.SUBMITTED
    assert engine.state.cash == Decimal("100")
    second = await engine.submit(
        _req(
            order_type=OrderType.LIMIT,
            price=Decimal("90000"),
            quantity=Decimal("0.01"),
            idempotency_key="second",
        ),
        _risk_ok(),
    )
    assert second.status == OrderStatus.FAILED
    assert second.metadata.get("error") == "insufficient_for_reserve"
    assert engine.state.reserved_cash == Decimal("900")
    assert engine.state.cash == Decimal("100")


@pytest.mark.asyncio
async def test_reject_does_not_reserve():
    engine = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    risk = RiskEvaluation(
        decision=RiskDecision.REJECTED,
        reason_code=RiskReasonCode.KILL_SWITCH_ACTIVE,
        message="halted",
    )
    order = await engine.submit(_req(), risk)
    assert order.status == OrderStatus.REJECTED
    assert engine.state.reserved_cash == Decimal("0")
    assert engine.state.cash == Decimal("10000")


def test_reservation_mismatch_invariant():
    report = check_cycle_invariants(
        cash=Decimal("9000"),
        reserved_cash=Decimal("1000"),
        positions={},
        realized_pnl=Decimal("0"),
        fills=[],
        orders={},
    )
    assert report.ok is False
    assert any(v.code == "RESERVATION_MISMATCH" for v in report.violations)
