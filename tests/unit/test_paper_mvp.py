"""Paper MVP unit tests — safety, config aliases, ema_rsi, broker, market facade."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.core.errors import LiveTradingDisabledError
from app.core.safety import SafetyGuard
from app.execution.broker import PaperBroker
from app.market_data.facade import MarketDataService, create_provider
from app.market_data.providers.bybit import BybitProvider
from app.models.domain.enums import (
    OrderSide,
    OrderType,
    RiskDecision,
    RiskReasonCode,
    SignalDirection,
)
from app.models.domain.market import Candle
from app.models.domain.trading import OrderRequest, PortfolioState, RiskEvaluation
from app.strategies.base import StrategyContext
from app.strategies.ema_rsi import EMARSIStrategy
from app.strategies.registry import get_strategy, list_strategies


def test_mvp_env_aliases():
    s = Settings(
        STARTING_BALANCE="12500",
        EXCHANGE_NAME="bybit",
        EXCHANGE_TESTNET="true",
        MAX_POSITION_RISK_PERCENT="1",
        MAX_POSITION_SIZE_PERCENT="20",
        TRADING_ENABLED="false",
        DEFAULT_SYMBOL="BTC/USDT",
        DEFAULT_TIMEFRAME="5m",
        FAST_EMA_PERIOD="9",
        SLOW_EMA_PERIOD="21",
        _env_file=None,
    )
    assert s.paper_starting_balance == Decimal("12500")
    assert s.exchange_id == "bybit"
    assert s.exchange_env == "testnet"
    assert s.max_risk_per_trade == Decimal("0.01")
    assert s.max_position_exposure == Decimal("0.20")
    assert s.trading_enabled is False
    assert s.default_timeframe == "5m"


def test_safety_blocks_futures_leverage_withdrawals():
    guard = SafetyGuard(Settings(_env_file=None))
    assert guard.check_order_intent(market_type="futures").allowed is False
    assert guard.check_order_intent(leverage=5).allowed is False
    assert guard.check_order_intent(action="withdraw").allowed is False
    assert guard.check_order_intent(market_type="spot", leverage=1).allowed is True


def test_safety_rejects_live_mode():
    s = Settings(trading_mode="live", _env_file=None)
    with pytest.raises(LiveTradingDisabledError):
        SafetyGuard(s).assert_paper_only()


def test_registry_includes_ema_rsi():
    ids = {s.strategy_id for s in list_strategies()}
    assert "ema_rsi" in ids
    assert get_strategy("ema_rsi").name == "EMA Crossover + RSI"


def test_ema_rsi_insufficient_history():
    strategy = EMARSIStrategy()
    cfg = strategy.default_config()
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    candles = [
        Candle(
            symbol="BTC/USDT",
            timeframe="5m",
            open_time=t0 + timedelta(minutes=5 * i),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("1"),
        )
        for i in range(10)
    ]
    signal = strategy.evaluate(
        StrategyContext(
            candles=candles,
            portfolio=PortfolioState(
                cash_balance=Decimal("10000"),
                equity=Decimal("10000"),
                peak_equity=Decimal("10000"),
            ),
            config=cfg,
        )
    )
    assert signal.direction == SignalDirection.HOLD
    assert "insufficient" in signal.entry_rationale.lower()


@pytest.mark.asyncio
async def test_paper_broker_idempotent_submit():
    broker = PaperBroker()
    risk = RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("0.01"),
    )
    broker.engine.set_mark_price("BTC/USDT", Decimal("100"))
    req = OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        idempotency_key="mvp-idemp-1",
        client_order_id="mvp-client-1",
    )
    first = await broker.submit_order(req, risk)
    second = await broker.submit_order(req, risk)
    assert first.id == second.id
    assert first.status.value == "FILLED"
    bal = await broker.get_balance()
    assert bal["cash"] < Decimal("10000")


def test_create_provider_bybit_default():
    s = Settings(EXCHANGE_NAME="bybit", _env_file=None)
    provider = create_provider(s)
    assert isinstance(provider, BybitProvider)


@pytest.mark.asyncio
async def test_market_facade_validate_normalize():
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    candles = [
        Candle(
            symbol="BTC/USDT",
            timeframe="5m",
            open_time=t0 + timedelta(minutes=5 * i),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("1"),
        )
        for i in range(3)
    ]
    svc = MarketDataService(provider=MagicMock())
    svc.provider.fetch_ohlcv = AsyncMock(return_value=candles)
    normalized = svc.normalize_candles(candles)
    assert all(c.open_time.tzinfo is not None for c in normalized)
    result = svc.validate_candles(normalized)
    assert result.ok is True
