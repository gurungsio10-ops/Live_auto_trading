"""Binance Spot Testnet WebSocket adapter tests."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from app.market_data.websocket.binance_spot import (
    BinanceSpotTestnetWebSocket,
    build_testnet_stream_url,
    symbol_to_stream,
)
from app.models.domain.market import Candle


def test_symbol_stream_and_url():
    assert symbol_to_stream("BTC/USDT") == "btcusdt"
    url = build_testnet_stream_url(
        ["BTC/USDT"], base_url="wss://stream.testnet.binance.vision/ws"
    )
    assert "stream.testnet.binance.vision" in url
    assert "btcusdt@kline_1m" in url
    assert "btcusdt@trade" in url
    assert "binance.com" not in url


@pytest.mark.asyncio
async def test_kline_closed_candle_callback():
    candles: list[Candle] = []

    async def on_candle(c: Candle) -> None:
        candles.append(c)

    class FakeTransport:
        def __init__(self) -> None:
            self.queue: asyncio.Queue = asyncio.Queue()
            self.closed = False

        async def connect(self, url: str) -> None:
            self.url = url

        async def send(self, raw: str) -> None:
            pass

        async def recv(self) -> str:
            return await self.queue.get()

        async def close(self) -> None:
            self.closed = True

    transport = FakeTransport()
    ws = BinanceSpotTestnetWebSocket(
        symbols=["BTC/USDT"],
        on_candle=on_candle,
        transport=transport,
        stale_seconds=60,
    )
    await ws.start()
    # Feed a combined-stream closed kline

    msg = {
        "stream": "btcusdt@kline_1m",
        "data": {
            "e": "kline",
            "s": "BTCUSDT",
            "k": {
                "t": 1_700_000_000_000,
                "T": 1_700_000_059_999,
                "s": "BTCUSDT",
                "i": "1m",
                "o": "100",
                "h": "110",
                "l": "90",
                "c": "105",
                "v": "12.5",
                "x": True,
            },
        },
    }
    # Inject via client handler directly for determinism
    await ws._handle_raw(msg)
    assert len(candles) == 1
    assert candles[0].symbol == "BTC/USDT"
    assert candles[0].close == Decimal("105")
    assert candles[0].is_closed is True

    # Duplicate trade protection
    trades: list[dict] = []

    async def on_trade(m: dict) -> None:
        trades.append(m)

    ws.on_trade = on_trade
    trade = {"e": "trade", "s": "BTCUSDT", "t": 42, "p": "105", "q": "0.01", "m": False}
    await ws._handle_raw(trade)
    await ws._handle_raw(trade)
    assert len(trades) == 1
    await ws.stop()
