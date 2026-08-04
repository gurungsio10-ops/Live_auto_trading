"""Candle source resolution: offline fixtures (default) or live public OHLCV."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.time import utc_now
from app.market_data.facade import MarketDataService
from app.models.domain.market import Candle
from app.services.paper_cycle import CandleSource, OfflineCandleSource

logger = get_logger("market.sources")

# Shared freshness stamp used by risk context.
_LAST_MARKET_DATA_TS = None


def last_market_data_ts():
    return _LAST_MARKET_DATA_TS


def touch_market_data_ts() -> None:
    global _LAST_MARKET_DATA_TS
    _LAST_MARKET_DATA_TS = utc_now()


class LivePublicCandleSource:
    """Fetch closed candles from public CCXT endpoints (Bybit/Binance)."""

    def __init__(self, service: MarketDataService | None = None) -> None:
        self.service = service or MarketDataService()

    async def load_closed_candles(
        self, symbol: str, timeframe: str, *, limit: int
    ) -> list[Candle]:
        candles = await self.service.load_closed_validated(
            symbol, timeframe, limit=limit
        )
        touch_market_data_ts()
        return candles

    async def close(self) -> None:
        await self.service.close()


async def resolve_candle_source(settings: Settings | None = None) -> CandleSource:
    cfg = settings or get_settings()
    if not cfg.use_live_market_data:
        touch_market_data_ts()  # offline fixtures are always "fresh"
        return OfflineCandleSource()
    try:
        source = LivePublicCandleSource()
        # Probe once so failures fall back for this cycle.
        await source.load_closed_candles(
            cfg.default_symbol, cfg.default_timeframe, limit=5
        )
        return source
    except Exception as exc:
        logger.warning(
            "live_market_data_fallback_offline",
            extra={"error": str(exc)},
        )
        touch_market_data_ts()
        return OfflineCandleSource()
