"""WebSocket market data ingestion with reconnect, heartbeat, and stale detection."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.core.time import ensure_utc, from_unix_ms, utc_now
from app.market_data.providers.retry import with_exponential_backoff

TickHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


@dataclass
class ConnectionMetrics:
    connects: int = 0
    disconnects: int = 0
    messages: int = 0
    duplicates: int = 0
    sequence_gaps: int = 0
    heartbeats: int = 0
    rest_fallbacks: int = 0
    last_message_at: datetime | None = None
    connected: bool = False


@dataclass
class WebSocketMarketDataClient:
    """
    Observation/paper-data feed only — not wired to order submission.

    `transport` is injectable for tests (no real network).
    """

    url: str
    symbols: list[str]
    stale_seconds: int | None = None
    on_tick: TickHandler | None = None
    transport: Any | None = None  # duck-typed WS connect/send/recv/close
    rest_fallback: Callable[[str], Awaitable[dict[str, Any]]] | None = None
    # Combined-stream URLs (Binance) already encode subscriptions — skip send.
    auto_subscribe: bool = True

    subscriptions: set[str] = field(default_factory=set)
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    _seen_ids: deque[str] = field(default_factory=lambda: deque(maxlen=10_000))
    _last_seq: int | None = None
    _running: bool = False
    _task: asyncio.Task | None = None

    def __post_init__(self) -> None:
        if self.stale_seconds is None:
            self.stale_seconds = get_settings().market_data_stale_seconds
        # Seed subscription set from symbols so REST fallback has a target.
        for symbol in self.symbols:
            self.subscriptions.add(symbol)

    @property
    def is_stale(self) -> bool:
        if self.metrics.last_message_at is None:
            return True
        age = utc_now() - ensure_utc(self.metrics.last_message_at)
        return age.total_seconds() > float(self.stale_seconds or 30)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self.transport is not None and hasattr(self.transport, "close"):
            await self.transport.close()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.metrics.connected = False

    async def subscribe(self, symbol: str) -> None:
        self.subscriptions.add(symbol)
        if self.metrics.connected and self.transport is not None:
            await self.transport.send(json.dumps({"op": "subscribe", "symbol": symbol}))

    async def unsubscribe(self, symbol: str) -> None:
        self.subscriptions.discard(symbol)
        if self.metrics.connected and self.transport is not None:
            await self.transport.send(
                json.dumps({"op": "unsubscribe", "symbol": symbol})
            )

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await with_exponential_backoff(
                    self._connect_and_consume, max_attempts=5, base_delay=0.05, jitter=0
                )
            except Exception:
                self.metrics.disconnects += 1
                self.metrics.connected = False
                if self.rest_fallback is not None and self.subscriptions:
                    symbol = next(iter(self.subscriptions))
                    await self.rest_fallback(symbol)
                    self.metrics.rest_fallbacks += 1
                await asyncio.sleep(0.05)

    async def _connect_and_consume(self) -> None:
        if self.transport is None:
            raise RuntimeError("No transport configured")
        await self.transport.connect(self.url)
        self.metrics.connects += 1
        self.metrics.connected = True
        if self.auto_subscribe:
            for symbol in list(self.subscriptions or self.symbols):
                await self.subscribe(symbol)
        while self._running:
            raw = await self.transport.recv()
            await self._handle_message(raw)

    async def _handle_message(self, raw: str | bytes | dict[str, Any]) -> None:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode()
        msg = json.loads(raw) if isinstance(raw, str) else raw

        if msg.get("type") == "heartbeat":
            self.metrics.heartbeats += 1
            self.metrics.last_message_at = utc_now()
            return

        msg_id = str(msg.get("id") or msg.get("trade_id") or "")
        if msg_id and msg_id in self._seen_ids:
            self.metrics.duplicates += 1
            return
        if msg_id:
            self._seen_ids.append(msg_id)

        seq = msg.get("sequence") or msg.get("seq")
        if seq is not None:
            seq_i = int(seq)
            if self._last_seq is not None and seq_i > self._last_seq + 1:
                self.metrics.sequence_gaps += 1
            self._last_seq = seq_i

        ts = msg.get("timestamp") or msg.get("T")
        if ts is not None:
            dt = (
                from_unix_ms(int(ts))
                if int(ts) > 10_000_000_000
                else datetime.fromtimestamp(int(ts), tz=UTC)
            )
            # Reject clearly future-dated nonsense (>1h ahead)
            if dt > utc_now().replace() and (dt - utc_now()).total_seconds() > 3600:
                return
            msg["timestamp_utc"] = dt.isoformat()

        if "price" in msg:
            msg["price"] = str(Decimal(str(msg["price"])))

        self.metrics.messages += 1
        self.metrics.last_message_at = utc_now()
        if self.on_tick:
            result = self.on_tick(msg)
            if asyncio.iscoroutine(result):
                await result
