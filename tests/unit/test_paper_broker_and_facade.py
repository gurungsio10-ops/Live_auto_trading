"""PaperBroker + MarketDataService facade coverage (mocked providers)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.core.safety import SafetyGuard
from app.execution.broker import PaperBroker
from app.execution.paper.engine import PaperConfig, PaperTradingEngine
from app.market_data.facade import (
    MarketDataService,
    create_provider,
    public_market_status,
)
from app.market_data.hub import MarketDataHub
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.market import Candle
from app.models.domain.trading import OrderRequest, RiskEvaluation


def _candle(i: int = 0) -> Candle:
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    return Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        open_time=t0 + timedelta(hours=i),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("10"),
        is_closed=True,
    )


@pytest.mark.asyncio
async def test_paper_broker_submit_cancel_balance_close():
    engine = PaperTradingEngine(
        PaperConfig(
            initial_cash=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            spread_rate=Decimal("0"),
        )
    )
    engine.set_mark_price("BTC/USDT", Decimal("100"))
    broker = PaperBroker(engine=engine)
    risk = RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("1"),
        message="ok",
    )
    order = await broker.submit_order(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            idempotency_key="broker-1",
        ),
        risk,
    )
    assert order.status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED}
    listed = await broker.list_orders()
    assert listed
    got = await broker.get_order(order.id)
    assert got is not None
    bal = await broker.get_balance()
    assert bal["cash"] < Decimal("10000")
    positions = await broker.get_positions()
    assert positions
    closed = await broker.close_position("BTC/USDT", mark_price=Decimal("100"))
    assert closed is not None
    cancelled = await broker.cancel_order("missing")
    assert cancelled is None


@pytest.mark.asyncio
async def test_paper_broker_safety_rejects_futures():
    guard = SafetyGuard(Settings(_env_file=None))
    broker = PaperBroker(safety=guard)
    # Force safety to reject by monkeypatching check
    broker.safety.check_order_intent = lambda **kw: type(
        "D", (), {"allowed": False, "code": "FUTURES", "reason": "blocked"}
    )()
    risk = RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("1"),
    )
    order = await broker.submit_order(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            idempotency_key="blocked-1",
        ),
        risk,
    )
    assert order.status == OrderStatus.REJECTED


@pytest.mark.asyncio
async def test_facade_load_validate_and_price():
    provider = MagicMock()
    provider.fetch_ohlcv = AsyncMock(return_value=[_candle(0), _candle(1)])
    provider.close = AsyncMock()
    provider.get_latest_price = AsyncMock(return_value=Decimal("100.5"))
    svc = MarketDataService(
        provider=provider, settings=Settings(trading_mode="paper", _env_file=None)
    )
    candles = await svc.load_closed_validated("BTC/USDT", "1h", limit=2)
    assert len(candles) == 2
    price = await svc.get_latest_price("BTC/USDT")
    assert price == Decimal("100.5")
    status = public_market_status(Settings(_env_file=None))
    assert status["requires_private_keys_for_ohlcv"] is False
    assert (
        create_provider(Settings(exchange_id="binance", _env_file=None)).name
        == "binance"
    )
    await svc.close()


@pytest.mark.asyncio
async def test_hub_success_and_failure_paths():
    provider = MagicMock()
    provider.fetch_ohlcv = AsyncMock(return_value=[_candle(0), _candle(1)])
    provider.close = AsyncMock()
    provider.get_latest_price = AsyncMock(return_value=Decimal("100.5"))
    settings = Settings(trading_mode="paper", _env_file=None)
    service = MarketDataService(provider=provider, settings=settings)
    hub = MarketDataHub(settings=settings, service=service)
    candles = await hub.load_closed_validated("BTC/USDT", "1h", limit=2)
    assert candles
    price = await hub.get_latest_price("BTC/USDT")
    assert price == Decimal("100.5")
    st = hub.status()
    assert st["fetch_ok"] >= 1
    provider.fetch_ohlcv = AsyncMock(side_effect=RuntimeError("down"))
    with pytest.raises(RuntimeError):
        await hub.load_closed_validated("BTC/USDT", "1h", limit=2)
    st2 = hub.status()
    assert st2["fetch_fail"] >= 1
