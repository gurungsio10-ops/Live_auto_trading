"""
Binance Spot Testnet WebSocket adapter.

Streams kline + trade messages into the generic ``WebSocketMarketDataClient``
pipeline. Uses official Spot Testnet stream host only.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.time import from_unix_ms, utc_now
from app.market_data.websocket.client import (
    ConnectionMetrics,
    WebSocketMarketDataClient,
)
from app.models.domain.market import Candle

logger = get_logger("market_data.binance_ws")

MessageHandler = Callable[[dict[str, Any]], Awaitable[None] | None]
CandleHandler = Callable[[Candle], Awaitable[None] | None]


def symbol_to_stream(symbol: str) -> str:
    """BTC/USDT → btcusdt"""
    return symbol.replace("/", "").replace("-", "").lower()


def build_testnet_stream_url(
    symbols: list[str],
    *,
    base_url: str | None = None,
    streams: tuple[str, ...] = ("kline_1m", "trade"),
) -> str:
    settings = get_settings()
    base = (base_url or settings.binance_testnet_ws_url).rstrip("/")
    # Combined stream endpoint
    if base.endswith("/ws"):
        base = base[: -len("/ws")] + "/stream"
    parts: list[str] = []
    for symbol in symbols:
        s = symbol_to_stream(symbol)
        for stream in streams:
            parts.append(f"{s}@{stream}")
    return f"{base}?streams={'/'.join(parts)}"


@dataclass
class BinanceSpotTestnetWebSocket:
    """
    High-level Binance Spot Testnet market stream.

    Wraps ``WebSocketMarketDataClient`` with Binance message decoding,
    stale-triggered reconnect, and candle/trade callbacks.
    """

    symbols: list[str]
    on_candle: CandleHandler | None = None
    on_trade: MessageHandler | None = None
    on_message: MessageHandler | None = None
    transport: Any | None = None
    rest_fallback: Callable[[str], Awaitable[dict[str, Any]]] | None = None
    stale_seconds: int | None = None
    client: WebSocketMarketDataClient | None = None
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    _seen_trade_ids: set[str] = field(default_factory=set)
    _last_kline_open: dict[str, int] = field(default_factory=dict)
    _watchdog_task: asyncio.Task | None = None

    def __post_init__(self) -> None:
        settings = get_settings()
        url = build_testnet_stream_url(self.symbols)
        self.client = WebSocketMarketDataClient(
            url=url,
            symbols=self.symbols,
            stale_seconds=self.stale_seconds or settings.market_data_stale_seconds,
            on_tick=self._handle_raw,
            transport=self.transport,
            rest_fallback=self.rest_fallback,
        )
        self.metrics = self.client.metrics

    @property
    def connected(self) -> bool:
        return bool(self.client and self.client.metrics.connected)

    @property
    def is_stale(self) -> bool:
        return bool(self.client and self.client.is_stale)

    @property
    def last_message_at(self):
        return self.client.metrics.last_message_at if self.client else None

    async def start(self) -> None:
        assert self.client is not None
        logger.info(
            "binance_ws_starting",
            extra={
                "symbols": self.symbols,
                "url_host": "stream.testnet.binance.vision",
            },
        )
        await self.client.start()
        # Watchdog: if stale while "connected", force reconnect.
        self._watchdog_task = asyncio.create_task(self._stale_watchdog())

    async def stop(self) -> None:
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None
        if self.client is not None:
            await self.client.stop()

    async def _stale_watchdog(self) -> None:
        assert self.client is not None
        while self.client._running:
            await asyncio.sleep(max(1, int(self.client.stale_seconds or 30) // 2))
            if self.client.metrics.connected and self.client.is_stale:
                logger.warning("binance_ws_stale_reconnect")
                self.client.metrics.disconnects += 1
                self.client.metrics.connected = False
                if self.client.transport is not None and hasattr(
                    self.client.transport, "close"
                ):
                    try:
                        await self.client.transport.close()
                    except Exception:
                        pass

    async def _handle_raw(self, payload: dict[str, Any]) -> None:
        # Combined stream wraps payload in {"stream": "...", "data": {...}}
        data = payload.get("data", payload)
        event = data.get("e") or payload.get("e")
        if event == "kline" or "k" in data:
            await self._handle_kline(data)
        elif event == "trade" or data.get("t") is not None:
            await self._handle_trade(data)
        if self.on_message is not None:
            maybe = self.on_message(payload)
            if maybe is not None:
                await maybe

    async def _handle_kline(self, data: dict[str, Any]) -> None:
        k = data.get("k") or data
        symbol_raw = str(k.get("s") or data.get("s") or "")
        symbol = _normalize_symbol(symbol_raw)
        open_ms = int(k.get("t") or 0)
        # Duplicate / out-of-order protection
        last = self._last_kline_open.get(symbol)
        is_closed = bool(k.get("x"))
        if last is not None and open_ms < last:
            return
        if last == open_ms and not is_closed:
            # update in-progress bar; only emit closed candles to strategy path
            pass
        if open_ms >= (last or 0):
            self._last_kline_open[symbol] = open_ms
        if not is_closed or self.on_candle is None:
            return
        candle = Candle(
            symbol=symbol,
            timeframe=_interval_to_tf(str(k.get("i") or "1m")),
            open_time=from_unix_ms(open_ms),
            open=Decimal(str(k["o"])),
            high=Decimal(str(k["h"])),
            low=Decimal(str(k["l"])),
            close=Decimal(str(k["c"])),
            volume=Decimal(str(k["v"])),
            close_time=from_unix_ms(int(k["T"])) if k.get("T") else None,
            is_closed=True,
        )
        maybe = self.on_candle(candle)
        if maybe is not None:
            await maybe

    async def _handle_trade(self, data: dict[str, Any]) -> None:
        trade_id = str(data.get("t") or data.get("id") or "")
        if trade_id and trade_id in self._seen_trade_ids:
            if self.client:
                self.client.metrics.duplicates += 1
            return
        if trade_id:
            self._seen_trade_ids.add(trade_id)
            if len(self._seen_trade_ids) > 20_000:
                # bound memory
                self._seen_trade_ids = set(list(self._seen_trade_ids)[-10_000:])
        if self.on_trade is None:
            return
        msg = {
            "symbol": _normalize_symbol(str(data.get("s") or "")),
            "price": str(data.get("p") or ""),
            "quantity": str(data.get("q") or ""),
            "trade_id": trade_id,
            "timestamp": utc_now().isoformat(),
            "is_buyer_maker": data.get("m"),
        }
        maybe = self.on_trade(msg)
        if maybe is not None:
            await maybe


def _normalize_symbol(raw: str) -> str:
    if not raw:
        return raw
    if "/" in raw:
        return raw.upper()
    raw = raw.upper()
    if raw.endswith("USDT"):
        return f"{raw[:-4]}/USDT"
    return raw


def _interval_to_tf(interval: str) -> str:
    return interval if interval else "1m"
