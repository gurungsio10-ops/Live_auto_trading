"""
Real WebSocket transport for market-data streaming.

Duck-typed interface matching the injectable FakeTransport used in tests:
``connect`` / ``send`` / ``recv`` / ``close``.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger

logger = get_logger("market_data.ws_transport")


class RealWebSocketTransport:
    """
    Production transport backed by the ``websockets`` library.

    Safe to construct without connecting; ``connect`` opens the socket.
    ``close`` unblocks any pending ``recv`` by cancelling the wait.
    """

    def __init__(
        self, *, ping_interval: float = 20.0, ping_timeout: float = 20.0
    ) -> None:
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout
        self._ws: Any | None = None
        self._url: str | None = None
        self._closed = False
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._closed

    async def connect(self, url: str) -> None:
        import websockets

        async with self._lock:
            await self._close_unlocked()
            self._closed = False
            self._url = url
            # Spot Testnet combined streams — no auth headers required for public data.
            self._ws = await websockets.connect(
                url,
                ping_interval=self._ping_interval,
                ping_timeout=self._ping_timeout,
                max_queue=1024,
                close_timeout=5,
            )
            logger.info(
                "ws_transport_connected",
                extra={"url_host": _host_of(url)},
            )

    async def send(self, data: str) -> None:
        if self._ws is None or self._closed:
            raise RuntimeError("WebSocket not connected")
        await self._ws.send(data)

    async def recv(self) -> str | bytes:
        if self._ws is None or self._closed:
            raise RuntimeError("WebSocket not connected")
        try:
            message = await self._ws.recv()
        except Exception as exc:
            # Normalize disconnects so the consumer loop can reconnect.
            raise RuntimeError(f"WebSocket recv failed: {type(exc).__name__}") from exc
        return message

    async def close(self) -> None:
        async with self._lock:
            await self._close_unlocked()

    async def _close_unlocked(self) -> None:
        self._closed = True
        ws = self._ws
        self._ws = None
        if ws is None:
            return
        try:
            await ws.close()
        except Exception:
            pass
        logger.info(
            "ws_transport_closed", extra={"url_host": _host_of(self._url or "")}
        )


def _host_of(url: str) -> str:
    # Avoid logging full query strings (stream lists can be long).
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"
