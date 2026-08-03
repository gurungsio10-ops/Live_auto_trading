"""Unit tests for RealWebSocketTransport (mocked websockets module)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.market_data.websocket.transport import RealWebSocketTransport, _host_of


def test_host_of_strips_query():
    assert (
        _host_of("wss://stream.testnet.binance.vision/stream?streams=btcusdt@trade")
        == "stream.testnet.binance.vision"
    )


@pytest.mark.asyncio
async def test_real_transport_connect_send_recv_close():
    fake_ws = AsyncMock()
    fake_ws.recv = AsyncMock(return_value='{"type":"heartbeat"}')
    fake_ws.send = AsyncMock()
    fake_ws.close = AsyncMock()

    with patch("websockets.connect", new=AsyncMock(return_value=fake_ws)) as connect:
        transport = RealWebSocketTransport(ping_interval=10, ping_timeout=5)
        await transport.connect("wss://stream.testnet.binance.vision/ws")
        assert transport.connected is True
        connect.assert_awaited_once()
        await transport.send("ping")
        fake_ws.send.assert_awaited_once_with("ping")
        msg = await transport.recv()
        assert msg == '{"type":"heartbeat"}'
        await transport.close()
        assert transport.connected is False
        fake_ws.close.assert_awaited()


@pytest.mark.asyncio
async def test_recv_without_connect_raises():
    transport = RealWebSocketTransport()
    with pytest.raises(RuntimeError, match="not connected"):
        await transport.recv()


@pytest.mark.asyncio
async def test_recv_normalizes_disconnect():
    fake_ws = MagicMock()
    fake_ws.recv = AsyncMock(side_effect=ConnectionError("gone"))
    fake_ws.close = AsyncMock()

    with patch("websockets.connect", new=AsyncMock(return_value=fake_ws)):
        transport = RealWebSocketTransport()
        await transport.connect("wss://example/ws")
        with pytest.raises(RuntimeError, match="recv failed"):
            await transport.recv()
