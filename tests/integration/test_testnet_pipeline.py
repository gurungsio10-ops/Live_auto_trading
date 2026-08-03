"""Integration: strategy → risk → mocked testnet execution → portfolio."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services.sample_market import build_ema_crossover_candles
from app.services.testnet_runtime import TestnetRuntime, reset_testnet_runtime


@pytest.fixture(autouse=True)
def _reset():
    reset_testnet_runtime()
    yield
    reset_testnet_runtime()


@pytest.mark.asyncio
async def test_end_to_end_mocked_testnet_cycle():
    api = MagicMock()
    api.load_markets = AsyncMock(return_value={})
    api.create_order = AsyncMock(
        return_value={
            "id": "ex-99",
            "filled": "0.001",
            "average": "65000",
            "amount": "0.001",
            "side": "buy",
            "type": "market",
            "status": "closed",
            "symbol": "BTC/USDT",
            "fee": {"cost": "0.05"},
        }
    )
    api.fetch_balance = AsyncMock(
        return_value={
            "free": {"USDT": "10000", "BTC": "0"},
            "used": {},
            "total": {"USDT": "10000", "BTC": "0"},
        }
    )

    settings = Settings(
        trading_mode="paper",
        exchange_env="testnet",
        exchange_api_key=SecretStr("k" * 24),
        exchange_api_secret=SecretStr("s" * 24),
        kill_switch_enabled=False,
        _env_file=None,
    )
    runtime = TestnetRuntime(
        settings=settings,
        exchange_api=api,
        strategy_id="ema_crossover",
        symbol="BTC/USDT",
    )
    runtime._ensure_backend()

    candles = build_ema_crossover_candles(force_buy_on_last=True)
    runtime._window = list(candles[:-1])
    result = await runtime.process_candle(candles[-1])

    assert result["accepted"] is True
    assert result["signal_direction"] == "buy"
    assert result["order_status"] == "FILLED"
    assert result["order_id"] == "ex-99"
    snap = runtime.dashboard_snapshot()
    assert Decimal(snap["available_usdt"]) < Decimal("10000")
    assert snap["stats"]["fills"] == 1
    assert snap["simulated_testnet"] is True


@pytest.mark.asyncio
async def test_kill_switch_blocks_testnet_order():
    api = MagicMock()
    api.load_markets = AsyncMock(return_value={})
    api.create_order = AsyncMock()
    settings = Settings(
        trading_mode="paper",
        exchange_env="testnet",
        exchange_api_key=SecretStr("k" * 24),
        exchange_api_secret=SecretStr("s" * 24),
        kill_switch_enabled=False,
        _env_file=None,
    )
    runtime = TestnetRuntime(settings=settings, exchange_api=api)
    runtime._ensure_backend()
    runtime.set_kill_switch(True)
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    runtime._window = list(candles[:-1])
    result = await runtime.process_candle(candles[-1])
    assert result["risk_reason_code"] == "KILL_SWITCH_ACTIVE"
    api.create_order.assert_not_called()
