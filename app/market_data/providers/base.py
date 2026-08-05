"""Base market data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from app.models.domain.market import Candle, SymbolInfo


class MarketDataProvider(ABC):
    """Abstract exchange/market-data provider."""

    name: str

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> Sequence[Candle]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_symbols(self) -> Sequence[SymbolInfo]:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> Sequence[Candle]:
        return await self.fetch_ohlcv(
            symbol, timeframe, since=since, until=until, limit=limit
        )

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        candles = await self.fetch_ohlcv(symbol, "1m", limit=1)
        if not candles:
            return {"symbol": symbol, "last": None, "available": False}
        last = candles[-1]
        return {
            "symbol": symbol,
            "last": str(last.close),
            "open": str(last.open),
            "high": str(last.high),
            "low": str(last.low),
            "volume": str(last.volume),
            "timestamp": last.open_time.isoformat(),
            "available": True,
        }

    async def get_order_book(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "bids": [],
            "asks": [],
            "available": False,
            "reason": "order_book_not_implemented_for_provider",
        }

    async def get_recent_trades(self, symbol: str) -> list[dict[str, Any]]:
        return []

    async def get_provider_status(self) -> dict[str, Any]:
        return {
            "provider": getattr(self, "name", "unknown"),
            "ok": True,
            "mode": getattr(self, "mode", "unknown"),
        }

    async def get_latency(self) -> int | None:
        return None

    async def get_last_update(self) -> str | None:
        return None
