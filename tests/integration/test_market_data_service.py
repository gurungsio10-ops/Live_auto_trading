"""Phase 2 integration: sync candles into DB via mocked provider."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.market_data.providers.binance import BinanceProvider
from app.market_data.service import MarketDataService
from app.models.database.market import CandleORM, SymbolORM
from app.models.domain.market import Candle, SymbolInfo


@pytest.mark.asyncio
async def test_sync_ohlcv_persists_candles(db_session):
    exchange = MagicMock()
    exchange.fetch_ohlcv = AsyncMock(
        return_value=[
            [1_700_000_000_000, 100.0, 110.0, 90.0, 105.0, 12.5],
            [1_700_000_060_000, 105.0, 115.0, 100.0, 110.0, 8.0],
        ]
    )
    provider = BinanceProvider(exchange=exchange)
    service = MarketDataService(provider, db_session)
    candles = await service.sync_ohlcv("BTC/USDT", "1m")
    assert len(candles) == 2

    rows = (await db_session.scalars(select(CandleORM))).all()
    assert len(rows) == 2
    assert rows[0].symbol == "BTC/USDT"
    assert rows[0].open == Decimal("100.0")

    loaded = await service.get_candles("BTC/USDT", "1m")
    assert len(loaded) == 2
    assert loaded[0].close == Decimal("105.0")
    await provider.close()


@pytest.mark.asyncio
async def test_sync_symbols_persists(db_session):
    provider = MagicMock()
    provider.fetch_symbols = AsyncMock(
        return_value=[
            SymbolInfo(
                symbol="BTC/USDT",
                base="BTC",
                quote="USDT",
                price_precision=2,
                quantity_precision=6,
                min_quantity=Decimal("0.0001"),
                min_notional=Decimal("10"),
                tick_size=Decimal("0.01"),
                step_size=Decimal("0.0001"),
            )
        ]
    )
    service = MarketDataService(provider, db_session)
    await service.sync_symbols()
    row = await db_session.scalar(select(SymbolORM).where(SymbolORM.symbol == "BTC/USDT"))
    assert row is not None
    assert row.base == "BTC"


@pytest.mark.asyncio
async def test_sync_ohlcv_rejects_broken_continuity(db_session):
    provider = MagicMock()
    provider.fetch_ohlcv = AsyncMock(
        return_value=[
            Candle(
                symbol="BTC/USDT",
                timeframe="1m",
                open_time=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105"),
                volume=Decimal("1"),
            ),
            Candle(
                symbol="BTC/USDT",
                timeframe="1m",
                open_time=datetime(2024, 1, 1, 0, 2, tzinfo=UTC),
                open=Decimal("105"),
                high=Decimal("115"),
                low=Decimal("100"),
                close=Decimal("110"),
                volume=Decimal("1"),
            ),
        ]
    )
    # Bypass BinanceProvider mapping — call service with a stub that returns Candles
    class Stub:
        async def fetch_ohlcv(self, *args, **kwargs):
            return await provider.fetch_ohlcv()

    service = MarketDataService(Stub(), db_session)
    from app.market_data.validators.candles import CandleValidationError

    with pytest.raises(CandleValidationError):
        await service.sync_ohlcv("BTC/USDT", "1m")
