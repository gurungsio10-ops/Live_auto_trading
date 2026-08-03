"""Phase 2: Binance provider with mocked exchange (no network)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.market_data.providers.binance import BinanceProvider


@pytest.mark.asyncio
async def test_fetch_ohlcv_maps_to_candles():
    exchange = MagicMock()
    exchange.fetch_ohlcv = AsyncMock(
        return_value=[
            [1_700_000_000_000, 100.0, 110.0, 90.0, 105.0, 12.5],
            [1_700_000_060_000, 105.0, 115.0, 100.0, 110.0, 8.0],
        ]
    )
    provider = BinanceProvider(exchange=exchange)
    candles = await provider.fetch_ohlcv("BTC/USDT", "1m")
    assert len(candles) == 2
    assert candles[0].symbol == "BTC/USDT"
    assert candles[0].open == Decimal("100.0")
    assert candles[0].open_time == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert candles[1].close == Decimal("110.0")
    exchange.fetch_ohlcv.assert_awaited_once()
    await provider.close()


@pytest.mark.asyncio
async def test_fetch_ohlcv_rejects_unsupported_symbol():
    exchange = MagicMock()
    provider = BinanceProvider(exchange=exchange)
    with pytest.raises(ValueError, match="Unsupported symbol"):
        await provider.fetch_ohlcv("ETH/USDT", "1m")
    await provider.close()


@pytest.mark.asyncio
async def test_fetch_ohlcv_retries_on_failure():
    exchange = MagicMock()
    exchange.fetch_ohlcv = AsyncMock(
        side_effect=[
            RuntimeError("rate limit"),
            [[1_700_000_000_000, 1, 2, 0.5, 1.5, 1]],
        ]
    )
    provider = BinanceProvider(exchange=exchange)
    candles = await provider.fetch_ohlcv("BTC/USDT", "1m")
    assert len(candles) == 1
    assert exchange.fetch_ohlcv.await_count == 2
    await provider.close()


@pytest.mark.asyncio
async def test_fetch_symbols_filters_supported():
    exchange = MagicMock()
    exchange.load_markets = AsyncMock(
        return_value={
            "BTC/USDT": {
                "base": "BTC",
                "quote": "USDT",
                "active": True,
                "precision": {"price": 2, "amount": 6},
                "limits": {"amount": {"min": 0.0001}, "cost": {"min": 10}},
                "info": {"tickSize": "0.01", "stepSize": "0.0001"},
            },
            "ETH/USDT": {
                "base": "ETH",
                "quote": "USDT",
                "active": True,
                "precision": {"price": 2, "amount": 4},
                "limits": {"amount": {"min": 0.001}, "cost": {"min": 10}},
                "info": {},
            },
        }
    )
    provider = BinanceProvider(exchange=exchange)
    symbols = await provider.fetch_symbols()
    assert len(symbols) == 1
    assert symbols[0].symbol == "BTC/USDT"
    assert symbols[0].min_notional == Decimal("10")
    await provider.close()


@pytest.mark.asyncio
async def test_provider_uses_configured_exchange_id(monkeypatch):
    monkeypatch.setenv("EXCHANGE_ID", "binanceus")
    from app.core.config import get_settings

    get_settings.cache_clear()
    provider = BinanceProvider()
    try:
        assert provider.exchange_id == "binanceus"
        assert provider.name == "binanceus"
        assert provider._owns_exchange is True
    finally:
        await provider.close()


def test_provider_rejects_unknown_exchange_id():
    with pytest.raises(ValueError, match="Unsupported exchange_id"):
        BinanceProvider(exchange_id="not-a-real-exchange")
