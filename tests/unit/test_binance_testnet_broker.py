"""Binance Spot Testnet broker unit tests (mocked API — no network)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.execution.exchange.precision import quantize_quantity
from app.execution.exchange.testnet import ExchangeTestnetClient
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.market import SymbolInfo
from app.models.domain.trading import OrderRequest, RiskEvaluation


def _approved() -> RiskEvaluation:
    return RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("0.01"),
    )


@pytest.mark.asyncio
async def test_submit_market_order_mocked():
    api = MagicMock()
    api.create_order = AsyncMock(
        return_value={
            "id": "tn-1",
            "filled": "0.01",
            "average": "100000",
            "amount": "0.01",
            "side": "buy",
            "type": "market",
            "status": "closed",
            "symbol": "BTC/USDT",
        }
    )
    api.load_markets = AsyncMock(return_value={})
    client = ExchangeTestnetClient(api=api)
    order = await client.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
            idempotency_key="tn-key",
        ),
        _approved(),
    )
    assert order.status == OrderStatus.FILLED
    assert order.id == "tn-1"
    api.create_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_idempotent_submit():
    api = MagicMock()
    api.create_order = AsyncMock(
        return_value={
            "id": "tn-2",
            "filled": "0.01",
            "average": "100000",
            "amount": "0.01",
            "side": "buy",
            "status": "closed",
            "symbol": "BTC/USDT",
        }
    )
    api.load_markets = AsyncMock(return_value={})
    client = ExchangeTestnetClient(api=api)
    req = OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        idempotency_key="same-key",
    )
    a = await client.submit(req, _approved())
    b = await client.submit(req, _approved())
    assert a.id == b.id
    assert api.create_order.await_count == 1


@pytest.mark.asyncio
async def test_fetch_balances():
    api = MagicMock()
    api.fetch_balance = AsyncMock(
        return_value={
            "free": {"USDT": "1000", "BTC": "0.1"},
            "used": {"USDT": "0", "BTC": "0"},
            "total": {"USDT": "1000", "BTC": "0.1"},
        }
    )
    client = ExchangeTestnetClient(api=api)
    bals = await client.fetch_balances()
    by_asset = {b.asset: b for b in bals}
    assert by_asset["USDT"].free == Decimal("1000")
    assert by_asset["BTC"].total == Decimal("0.1")


@pytest.mark.asyncio
async def test_cancel_and_status():
    api = MagicMock()
    api.fetch_order = AsyncMock(
        return_value={
            "id": "1",
            "status": "open",
            "side": "buy",
            "type": "limit",
            "amount": "0.01",
            "filled": "0",
            "symbol": "BTC/USDT",
            "price": "50000",
        }
    )
    api.cancel_order = AsyncMock(
        return_value={
            "id": "1",
            "status": "canceled",
            "side": "buy",
            "type": "limit",
            "amount": "0.01",
            "filled": "0",
            "symbol": "BTC/USDT",
        }
    )
    client = ExchangeTestnetClient(api=api)
    status = await client.fetch_order("1", "BTC/USDT")
    assert status.status == OrderStatus.SUBMITTED
    cancelled = await client.cancel_order("1", "BTC/USDT")
    assert cancelled.status == OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_limit_order_precision():
    api = MagicMock()
    api.load_markets = AsyncMock(
        return_value={
            "BTC/USDT": {
                "symbol": "BTC/USDT",
                "base": "BTC",
                "quote": "USDT",
                "active": True,
                "precision": {"price": 2, "amount": 5},
                "limits": {
                    "amount": {"min": 0.00001},
                    "cost": {"min": 10},
                },
                "info": {
                    "filters": [
                        {
                            "filterType": "LOT_SIZE",
                            "stepSize": "0.00001",
                            "minQty": "0.00001",
                        },
                        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                        {"filterType": "NOTIONAL", "minNotional": "10"},
                    ]
                },
            }
        }
    )
    api.create_order = AsyncMock(
        return_value={
            "id": "L1",
            "status": "open",
            "side": "buy",
            "type": "limit",
            "amount": "0.001",
            "filled": "0",
            "price": "50000.00",
            "symbol": "BTC/USDT",
            "clientOrderId": "c1",
        }
    )
    client = ExchangeTestnetClient(api=api)
    order = await client.place_limit_order(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.001234567"),
        price=Decimal("50000.129"),
        client_order_id="c1",
    )
    assert order.id == "L1"
    info = await client.fetch_symbol_info("BTC/USDT")
    assert quantize_quantity(Decimal("0.001234567"), info) == Decimal("0.00123")


def test_symbol_info_defaults():
    info = SymbolInfo(
        symbol="BTC/USDT",
        base="BTC",
        quote="USDT",
        price_precision=2,
        quantity_precision=5,
        min_quantity=Decimal("0.00001"),
        min_notional=Decimal("10"),
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.00001"),
    )
    assert info.min_notional == Decimal("10")
