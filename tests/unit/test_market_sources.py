"""Candle source resolution: offline default and live fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings, get_settings
from app.services import market_sources
from app.services.market_sources import (
    LivePublicCandleSource,
    resolve_candle_source,
    touch_market_data_ts,
)
from app.services.paper_cycle import OfflineCandleSource


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_resolve_offline_by_default():
    settings = Settings(
        use_live_market_data=False, trading_mode="paper", _env_file=None
    )
    source = await resolve_candle_source(settings)
    assert isinstance(source, OfflineCandleSource)
    assert market_sources.last_market_data_ts() is not None


@pytest.mark.asyncio
async def test_resolve_live_falls_back_on_probe_failure(monkeypatch):
    settings = Settings(use_live_market_data=True, trading_mode="paper", _env_file=None)

    class Boom:
        async def load_closed_candles(self, *a, **k):
            raise RuntimeError("exchange down")

        async def close(self) -> None:
            return None

    monkeypatch.setattr(market_sources, "LivePublicCandleSource", lambda: Boom())
    source = await resolve_candle_source(settings)
    assert isinstance(source, OfflineCandleSource)


@pytest.mark.asyncio
async def test_live_public_source_delegates():
    svc = MagicMock()
    svc.load_closed_validated = AsyncMock(return_value=[])
    svc.close = AsyncMock()
    src = LivePublicCandleSource(service=svc)
    await src.load_closed_candles("BTC/USDT", "1h", limit=10)
    svc.load_closed_validated.assert_awaited_once()
    await src.close()
    touch_market_data_ts()
    assert market_sources.last_market_data_ts() is not None
