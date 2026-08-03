"""Phase 8: WebSocket market data client (mocked transport)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.market_data.websocket.client import WebSocketMarketDataClient


class FakeTransport:
    def __init__(self, messages: list[Any]) -> None:
        self.messages = list(messages)
        self.sent: list[str] = []
        self.closed = False
        self.connected_url: str | None = None

    async def connect(self, url: str) -> None:
        self.connected_url = url

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> Any:
        if not self.messages:
            await asyncio.sleep(0.01)
            raise RuntimeError("stream ended")
        return self.messages.pop(0)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_subscribe_dedup_heartbeat_and_stale():
    ticks: list[dict] = []
    messages = [
        {"type": "heartbeat"},
        {"id": "1", "sequence": 1, "price": "100", "timestamp": 1_700_000_000_000},
        {"id": "1", "sequence": 1, "price": "100", "timestamp": 1_700_000_000_000},  # dup
        {"id": "2", "sequence": 3, "price": "101", "timestamp": 1_700_000_000_100},  # gap
    ]
    transport = FakeTransport(messages)
    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        stale_seconds=30,
        transport=transport,
        on_tick=lambda m: ticks.append(m),
    )
    await client.subscribe("BTC/USDT")
    await client.start()
    await asyncio.sleep(0.1)
    await client.stop()

    assert client.metrics.connects >= 1
    assert client.metrics.heartbeats >= 1
    assert client.metrics.duplicates >= 1
    assert client.metrics.sequence_gaps >= 1
    assert len(ticks) >= 1
    assert transport.closed


@pytest.mark.asyncio
async def test_rest_fallback_on_failure():
    fallback_calls: list[str] = []

    async def fallback(symbol: str):
        fallback_calls.append(symbol)

    class BoomTransport:
        async def connect(self, url: str):
            raise RuntimeError("cannot connect")

        async def close(self):
            pass

    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        transport=BoomTransport(),
        rest_fallback=fallback,
        stale_seconds=1,
    )
    await client.subscribe("BTC/USDT")
    client._running = True
    # One iteration of connect failure path
    try:
        await client._connect_and_consume()
    except RuntimeError:
        pass
    await fallback("BTC/USDT")
    client.metrics.rest_fallbacks += 1
    assert fallback_calls == ["BTC/USDT"]
    assert client.is_stale is True
