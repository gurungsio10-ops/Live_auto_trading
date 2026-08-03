"""Binance OHLCV provider via ccxt (REST)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

import ccxt.async_support as ccxt

from app.core.config import get_settings
from app.core.time import ensure_utc, from_unix_ms, to_unix_ms
from app.market_data.normalizers.timestamps import normalize_candle_timestamps
from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.retry import with_exponential_backoff
from app.models.domain.market import Candle, SymbolInfo

_SUPPORTED_EXCHANGES = {
    "binance": ccxt.binance,
    "binanceus": ccxt.binanceus,
}


class BinanceProvider(MarketDataProvider):
    name = "binance"

    def __init__(
        self,
        *,
        exchange: Any | None = None,
        exchange_id: str | None = None,
        sandbox: bool | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        settings = get_settings()
        if exchange is not None:
            self._exchange = exchange
            self._owns_exchange = False
            self.exchange_id = exchange_id or settings.exchange_id
        else:
            resolved_id = (exchange_id or settings.exchange_id).lower().strip()
            factory = _SUPPORTED_EXCHANGES.get(resolved_id)
            if factory is None:
                supported = ", ".join(sorted(_SUPPORTED_EXCHANGES))
                raise ValueError(
                    f"Unsupported exchange_id '{resolved_id}'. Supported: {supported}"
                )
            use_sandbox = (
                sandbox if sandbox is not None else settings.exchange_env == "testnet"
            )
            self._exchange = factory(
                {
                    "apiKey": api_key
                    or (
                        settings.exchange_api_key.get_secret_value()
                        if settings.exchange_api_key
                        else ""
                    ),
                    "secret": api_secret
                    or (
                        settings.exchange_api_secret.get_secret_value()
                        if settings.exchange_api_secret
                        else ""
                    ),
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                }
            )
            if use_sandbox and hasattr(self._exchange, "set_sandbox_mode"):
                self._exchange.set_sandbox_mode(True)
            self._owns_exchange = True
            self.exchange_id = resolved_id
            self.name = resolved_id

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
        if timeframe not in settings.supported_timeframes:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        since_ms = to_unix_ms(ensure_utc(since)) if since else None
        until_ms = to_unix_ms(ensure_utc(until)) if until else None

        async def _call() -> list[list[Any]]:
            return await self._exchange.fetch_ohlcv(
                symbol, timeframe=timeframe, since=since_ms, limit=limit
            )

        raw = await with_exponential_backoff(_call, max_attempts=5, base_delay=0.05)
        candles: list[Candle] = []
        for row in raw:
            open_ms, o, h, l, c, v = row[:6]
            if until_ms is not None and int(open_ms) > until_ms:
                continue
            candle = Candle(
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
            candles.append(normalize_candle_timestamps(candle))
        return candles

    async def fetch_symbols(self) -> Sequence[SymbolInfo]:
        async def _call() -> dict[str, Any]:
            return await self._exchange.load_markets()

        markets = await with_exponential_backoff(_call, max_attempts=5, base_delay=0.05)
        results: list[SymbolInfo] = []
        for symbol, market in markets.items():
            if symbol not in get_settings().supported_symbols:
                continue
            precision = market.get("precision") or {}
            limits = market.get("limits") or {}
            amount_limits = limits.get("amount") or {}
            cost_limits = limits.get("cost") or {}
            results.append(
                SymbolInfo(
                    symbol=symbol,
                    base=market.get("base") or symbol.split("/")[0],
                    quote=market.get("quote") or symbol.split("/")[1],
                    price_precision=int(precision.get("price") or 8),
                    quantity_precision=int(precision.get("amount") or 8),
                    min_quantity=Decimal(str(amount_limits.get("min") or "0.0001")),
                    min_notional=Decimal(str(cost_limits.get("min") or "10")),
                    tick_size=Decimal(
                        str((market.get("info") or {}).get("tickSize") or "0.01")
                    ),
                    step_size=Decimal(
                        str((market.get("info") or {}).get("stepSize") or "0.0001")
                    ),
                    active=bool(market.get("active", True)),
                )
            )
        return results

    async def close(self) -> None:
        if self._owns_exchange:
            await self._exchange.close()
