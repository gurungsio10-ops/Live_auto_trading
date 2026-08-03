"""Testnet runtime hydrate + REST cycle helpers."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.time import utc_now
from app.models.domain.market import Candle
from app.services.testnet_runtime import TestnetRuntime, reset_testnet_runtime


@pytest.fixture(autouse=True)
def _reset():
    reset_testnet_runtime()
    yield
    reset_testnet_runtime()


def _settings() -> Settings:
    return Settings(
        trading_mode="paper",
        exchange_env="testnet",
        exchange_api_key=SecretStr("k" * 24),
        exchange_api_secret=SecretStr("s" * 24),
        kill_switch_enabled=False,
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_hydrate_from_exchange_balances_and_orders():
    api = MagicMock()
    api.load_markets = AsyncMock(return_value={})
    api.fetch_balance = AsyncMock(
        return_value={
            "free": {"USDT": "8000", "BTC": "0.01"},
            "used": {"USDT": "0", "BTC": "0"},
            "total": {"USDT": "8000", "BTC": "0.01"},
        }
    )
    api.fetch_open_orders = AsyncMock(
        return_value=[
            {
                "id": "open-1",
                "symbol": "BTC/USDT",
                "side": "buy",
                "type": "limit",
                "amount": "0.001",
                "filled": "0",
                "status": "open",
                "price": "60000",
                "clientOrderId": "c1",
            }
        ]
    )
    api.create_order = AsyncMock()

    runtime = TestnetRuntime(
        settings=_settings(),
        exchange_api=api,
        enable_websocket=False,
    )
    await runtime.start()

    assert runtime.local_portfolio.balances["USDT"] == Decimal("8000")
    assert runtime.local_portfolio.balances["BTC"] == Decimal("0.01")
    assert runtime.local_portfolio.positions["BTC/USDT"] == Decimal("0.01")
    assert any(o.id == "open-1" for o in runtime._orders)
    await runtime.stop()


@pytest.mark.asyncio
async def test_run_rest_cycle_processes_tip_candle():
    api = MagicMock()
    api.load_markets = AsyncMock(return_value={})
    api.create_order = AsyncMock(
        return_value={
            "id": "ex-rest",
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
            "free": {"USDT": "10000"},
            "used": {},
            "total": {"USDT": "10000"},
        }
    )

    runtime = TestnetRuntime(
        settings=_settings(),
        exchange_api=api,
        enable_websocket=False,
    )
    runtime._ensure_backend()

    from app.services.sample_market import build_ema_crossover_candles

    candles = build_ema_crossover_candles(force_buy_on_last=True)
    with patch.object(
        runtime, "fetch_rest_candles", new=AsyncMock(return_value=candles)
    ):
        result = await runtime.run_rest_cycle(lookback=60)

    assert result["accepted"] is True
    assert result["signal_direction"] == "buy"
    assert result["order_status"] == "FILLED"


@pytest.mark.asyncio
async def test_rest_fallback_gap_recovery():
    runtime = TestnetRuntime(
        settings=_settings(),
        exchange_api=MagicMock(),
        enable_websocket=False,
    )
    runtime._ensure_backend()
    tip = Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=utc_now().replace(second=0, microsecond=0),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("1"),
        is_closed=True,
    )
    # Need enough window for strategy — inject via process path carefully.
    with (
        patch.object(runtime, "fetch_rest_candles", new=AsyncMock(return_value=[tip])),
        patch.object(
            runtime, "on_closed_candle", new=AsyncMock(return_value={"accepted": True})
        ) as on_closed,
    ):
        out = await runtime._rest_fallback("BTC/USDT")
    assert out["candles_fetched"] == 1
    assert out["candles_processed"] == 1
    on_closed.assert_awaited_once()
