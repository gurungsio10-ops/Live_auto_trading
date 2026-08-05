"""Paper broker: stop/tp, cancel, expire, maker/taker fees."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.execution.paper.engine import PaperConfig, PaperTradingEngine
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.trading import OrderRequest, RiskEvaluation


def _risk(qty: str = "1") -> RiskEvaluation:
    return RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal(qty),
        message="ok",
    )


@pytest.mark.asyncio
async def test_stop_loss_rests_then_triggers_on_mark():
    engine = PaperTradingEngine(
        PaperConfig(
            initial_cash=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            spread_rate=Decimal("0"),
        )
    )
    engine.set_mark_price("BTC/USDT", Decimal("100"))
    # Open long first
    buy = await engine.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            idempotency_key="buy-1",
        ),
        _risk(),
    )
    assert buy.status == OrderStatus.FILLED

    stop = await engine.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LOSS,
            quantity=Decimal("1"),
            price=Decimal("90"),
            idempotency_key="stop-1",
        ),
        _risk(),
    )
    assert stop.status == OrderStatus.SUBMITTED
    engine.set_mark_price("BTC/USDT", Decimal("89"))
    updated = engine.state.orders[stop.id]
    assert updated.status == OrderStatus.FILLED
    assert "BTC/USDT" not in engine.state.positions


@pytest.mark.asyncio
async def test_take_profit_and_cancel_and_expire():
    engine = PaperTradingEngine(
        PaperConfig(
            initial_cash=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            spread_rate=Decimal("0"),
            maker_fee_rate=Decimal("0.0005"),
            taker_fee_rate=Decimal("0.001"),
        )
    )
    engine.set_mark_price("BTC/USDT", Decimal("100"))
    await engine.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            idempotency_key="buy-2",
        ),
        _risk(),
    )
    tp = await engine.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.TAKE_PROFIT,
            quantity=Decimal("1"),
            price=Decimal("120"),
            idempotency_key="tp-1",
        ),
        _risk(),
    )
    assert tp.status == OrderStatus.SUBMITTED
    cancelled = await engine.cancel(tp.id)
    assert cancelled.status == OrderStatus.CANCELLED

    limit = await engine.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),
            price=Decimal("150"),
            idempotency_key="limit-1",
        ),
        _risk(),
    )
    assert limit.status == OrderStatus.SUBMITTED
    expired = await engine.expire(limit.id)
    assert expired.status == OrderStatus.EXPIRED


@pytest.mark.asyncio
async def test_liquidity_reject_deterministic_with_seed():
    engine = PaperTradingEngine(
        PaperConfig(
            initial_cash=Decimal("10000"),
            reject_probability=Decimal("1"),
            seed=42,
        )
    )
    engine.set_mark_price("BTC/USDT", Decimal("100"))
    order = await engine.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
            idempotency_key="rej-1",
        ),
        _risk("0.01"),
    )
    assert order.status == OrderStatus.REJECTED
    assert order.metadata.get("error") == "insufficient_liquidity"
