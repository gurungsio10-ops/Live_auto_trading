"""Base market data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

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
