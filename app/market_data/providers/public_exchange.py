"""Public exchange market data via ccxt — no trading credentials required."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

import ccxt.async_support as ccxt

from app.core.config import get_settings
from app.core.time import ensure_utc, from_unix_ms, to_unix_ms, utc_now
from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.retry import with_exponential_backoff
from app.models.domain.market import Candle, SymbolInfo


class PublicExchangeMarketDataProvider(MarketDataProvider):
    """
    Read-only public market data (Binance spot by default).

    Does not require API keys. Trading remains paper — this provider never places orders.
    """

    name = "public_exchange"
    mode = "public_live_market_data"

    def __init__(self, *, exchange_id: str = "binance", exchange: Any | None = None) -> None:
        self._last_update: datetime | None = None
        self._last_latency_ms: int | None = None
        if exchange is not None:
            self._exchange = exchange
            self._owns_exchange = False
        else:
            factory = getattr(ccxt, exchange_id, None) or ccxt.binance
            self._exchange = factory(
                {
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                }
            )
            self._owns_exchange = True

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> Sequence[Candle]:
        settings = get_settings()
        if symbol not in settings.supported_symbols:
            raise ValueError(f"Unsupported symbol: {symbol}")
        since_ms = to_unix_ms(ensure_utc(since)) if since else None
        until_ms = to_unix_ms(ensure_utc(until)) if until else None
        started = utc_now()

        async def _call() -> list[list[Any]]:
            return await self._exchange.fetch_ohlcv(
                symbol, timeframe=timeframe, since=since_ms, limit=limit
            )

        raw = await with_exponential_backoff(_call, max_attempts=4, base_delay=0.1)
        self._last_latency_ms = int((utc_now() - started).total_seconds() * 1000)
        candles: list[Candle] = []
        for row in raw:
            open_ms, o, h, l, c, v = row[:6]
            if until_ms is not None and int(open_ms) > until_ms:
                continue
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=from_unix_ms(int(open_ms)),
                    open=Decimal(str(o)),
                    high=Decimal(str(h)),
                    low=Decimal(str(l)),
                    close=Decimal(str(c)),
                    volume=Decimal(str(v)),
                    is_closed=True,
                )
            )
        if candles:
            self._last_update = ensure_utc(candles[-1].open_time)
        return candles

    async def fetch_symbols(self) -> Sequence[SymbolInfo]:
        settings = get_settings()
        return [
            SymbolInfo(
                symbol=sym,
                base=sym.split("/")[0],
                quote=sym.split("/")[1] if "/" in sym else "USDT",
                price_precision=2,
                quantity_precision=8,
                min_quantity=Decimal("0.00001"),
                min_notional=Decimal("10"),
                tick_size=Decimal("0.01"),
                step_size=Decimal("0.00001"),
                active=True,
            )
            for sym in settings.supported_symbols
        ]

    async def close(self) -> None:
        if self._owns_exchange:
            await self._exchange.close()

    async def get_provider_status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "mode": self.mode,
            "ok": True,
            "label": "Public exchange market data (paper trading still simulated)",
            "latency_ms": self._last_latency_ms,
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

    async def get_latency(self) -> int | None:
        return self._last_latency_ms

    async def get_last_update(self) -> str | None:
        return self._last_update.isoformat() if self._last_update else None
