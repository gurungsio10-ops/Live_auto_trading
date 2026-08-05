"""Market-data facade used by the paper MVP orchestrator."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from app.core.config import Settings, get_settings
from app.market_data.normalizers.timestamps import normalize_candle_timestamps
from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.binance import BinanceProvider
from app.market_data.providers.bybit import BybitProvider
from app.market_data.validators.candles import ValidationResult, validate_candles
from app.models.domain.market import Candle


def create_provider(settings: Settings | None = None) -> MarketDataProvider:
    cfg = settings or get_settings()
    exchange = (cfg.exchange_id or "bybit").lower().strip()
    if exchange == "binance":
        return BinanceProvider()
    return BybitProvider()


class MarketDataService:
    """Thin adapter: fetch → validate → normalize."""

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or create_provider(self.settings)

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, *, limit: int = 200
    ) -> Sequence[Candle]:
        return await self.provider.fetch_ohlcv(symbol, timeframe, limit=limit)

    async def get_latest_price(self, symbol: str) -> Decimal:
        getter = getattr(self.provider, "get_latest_price", None)
        if callable(getter):
            return await getter(symbol)
        candles = await self.fetch_ohlcv(
            symbol, self.settings.default_timeframe, limit=1
        )
        if not candles:
            raise ValueError(f"No candles available for {symbol}")
        return candles[-1].close

    def validate_candles(self, candles: Sequence[Candle]) -> ValidationResult:
        return validate_candles(list(candles))

    def normalize_candles(self, candles: Sequence[Candle]) -> list[Candle]:
        return [normalize_candle_timestamps(c) for c in candles]

    async def load_closed_validated(
        self, symbol: str, timeframe: str, *, limit: int = 200
    ) -> list[Candle]:
        raw = list(await self.fetch_ohlcv(symbol, timeframe, limit=limit))
        normalized = self.normalize_candles(raw)
        closed = [c for c in normalized if c.is_closed]
        result = self.validate_candles(closed)
        if not result.ok:
            codes = [i.code for i in result.issues]
            raise ValueError(f"Candle validation failed: {codes}")
        return closed

    async def close(self) -> None:
        await self.provider.close()


def public_market_status(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    return {
        "exchange_id": cfg.exchange_id,
        "exchange_env": cfg.exchange_env,
        "default_symbol": cfg.default_symbol,
        "default_timeframe": cfg.default_timeframe,
        "requires_private_keys_for_ohlcv": False,
        "note": "Public OHLCV via CCXT; paper cycles default to offline fixtures",
    }
