"""Phase 8: WebSocket market data client (mocked transport)."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from app.core.time import utc_now
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
        {
            "id": "1",
            "sequence": 1,
            "price": "100",
            "timestamp": 1_700_000_000_000,
        },  # dup
        {
            "id": "2",
            "sequence": 3,
            "price": "101",
            "timestamp": 1_700_000_000_100,
        },  # gap
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
    assert ticks[0]["price"] == str(Decimal("100"))


@pytest.mark.asyncio
async def test_rest_fallback_via_run_loop(monkeypatch):
    fallback_calls: list[str] = []

    async def fallback(symbol: str):
        fallback_calls.append(symbol)

    class BoomTransport:
        async def connect(self, url: str):
            raise RuntimeError("cannot connect")

        async def close(self):
            pass

    async def fail_fast(fn, **kwargs):
        await fn()

    monkeypatch.setattr(
        "app.market_data.websocket.client.with_exponential_backoff",
        fail_fast,
    )

    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        transport=BoomTransport(),
        rest_fallback=fallback,
        stale_seconds=1,
    )
    await client.subscribe("BTC/USDT")
    await client.start()
    await asyncio.sleep(0.15)
    await client.stop()
    assert fallback_calls
    assert client.metrics.rest_fallbacks >= 1
    assert client.metrics.disconnects >= 1
    assert client.is_stale is True


@pytest.mark.asyncio
async def test_is_stale_false_when_recent_message():
    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        stale_seconds=30,
        transport=FakeTransport([]),
    )
    client.metrics.last_message_at = utc_now()
    assert client.is_stale is False
    client.metrics.last_message_at = utc_now() - timedelta(seconds=60)
    assert client.is_stale is True


@pytest.mark.asyncio
async def test_unsubscribe_sends_when_connected():
    transport = FakeTransport([{"type": "heartbeat"}])
    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        transport=transport,
        stale_seconds=30,
    )
    await client.subscribe("BTC/USDT")
    client.metrics.connected = True
    await client.unsubscribe("BTC/USDT")
    assert "BTC/USDT" not in client.subscriptions
    assert any('"unsubscribe"' in s for s in transport.sent)


@pytest.mark.asyncio
async def test_handles_json_string_and_bytes_messages():
    ticks: list[dict] = []
    payload = {
        "id": "b1",
        "sequence": 1,
        "price": 99.5,
        "timestamp": int(utc_now().timestamp()),
    }
    messages = [
        json.dumps(payload),
        json.dumps({**payload, "id": "b2", "sequence": 2}).encode(),
    ]
    transport = FakeTransport(messages)
    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        transport=transport,
        on_tick=lambda m: ticks.append(m),
        stale_seconds=30,
    )
    await client.subscribe("BTC/USDT")
    await client.start()
    await asyncio.sleep(0.1)
    await client.stop()
    assert len(ticks) == 2
    assert ticks[0]["price"] == "99.5"
    assert "timestamp_utc" in ticks[0]


@pytest.mark.asyncio
async def test_async_on_tick_is_awaited():
    seen: list[str] = []

    async def on_tick(msg: dict[str, Any]) -> None:
        seen.append(msg["id"])

    transport = FakeTransport(
        [{"id": "a1", "sequence": 1, "price": "1", "timestamp": 1_700_000_000_000}]
    )
    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        transport=transport,
        on_tick=on_tick,
        stale_seconds=30,
    )
    await client.subscribe("BTC/USDT")
    await client.start()
    await asyncio.sleep(0.1)
    await client.stop()
    assert seen == ["a1"]


@pytest.mark.asyncio
async def test_rejects_far_future_timestamp():
    ticks: list[dict] = []
    future_ms = int((utc_now() + timedelta(hours=5)).timestamp() * 1000)
    transport = FakeTransport(
        [{"id": "fut", "sequence": 1, "price": "1", "timestamp": future_ms}]
    )
    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        transport=transport,
        on_tick=lambda m: ticks.append(m),
        stale_seconds=30,
    )
    await client.subscribe("BTC/USDT")
    await client.start()
    await asyncio.sleep(0.1)
    await client.stop()
    assert ticks == []
    assert client.metrics.messages == 0


@pytest.mark.asyncio
async def test_no_transport_raises():
    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        transport=None,
        stale_seconds=30,
    )
    with pytest.raises(RuntimeError, match="No transport configured"):
        await client._connect_and_consume()


def test_default_stale_seconds_from_settings(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_STALE_SECONDS", "42")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client = WebSocketMarketDataClient(
        url="wss://example/ws",
        symbols=["BTC/USDT"],
        transport=FakeTransport([]),
    )
    assert client.stale_seconds == 42


def test_websocket_client_not_imported_by_execution():
    """Phase 8 feed must remain advisory/observation-only vs order path."""
    import inspect

    import app.execution.gateway as gateway
    import app.execution.paper.engine as paper

    for mod in (gateway, paper):
        src = inspect.getsource(mod)
        assert "WebSocketMarketDataClient" not in src
        assert "market_data.websocket" not in src
