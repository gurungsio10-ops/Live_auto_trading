"""Historical market data service: fetch, validate, persist."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.market_data.normalizers.timestamps import normalize_candles
from app.market_data.providers.base import MarketDataProvider
from app.market_data.validators.candles import validate_candles
from app.models.database.market import CandleORM, SymbolORM
from app.models.domain.market import Candle, SymbolInfo


class MarketDataService:
    def __init__(self, provider: MarketDataProvider, session: AsyncSession) -> None:
        self.provider = provider
        self.session = session

    async def sync_symbols(self) -> Sequence[SymbolInfo]:
        symbols = await self.provider.fetch_symbols()
        now = utc_now()
        for info in symbols:
            existing = await self.session.scalar(
                select(SymbolORM).where(SymbolORM.symbol == info.symbol)
            )
            if existing is None:
                self.session.add(
                    SymbolORM(
                        symbol=info.symbol,
                        base=info.base,
                        quote=info.quote,
                        price_precision=info.price_precision,
                        quantity_precision=info.quantity_precision,
                        min_quantity=info.min_quantity,
                        min_notional=info.min_notional,
                        tick_size=info.tick_size,
                        step_size=info.step_size,
                        active=info.active,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                existing.base = info.base
                existing.quote = info.quote
                existing.price_precision = info.price_precision
                existing.quantity_precision = info.quantity_precision
                existing.min_quantity = info.min_quantity
                existing.min_notional = info.min_notional
                existing.tick_size = info.tick_size
                existing.step_size = info.step_size
                existing.active = info.active
                existing.updated_at = now
        await self.session.commit()
        return symbols

    async def sync_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> list[Candle]:
        candles = list(
            await self.provider.fetch_ohlcv(
                symbol, timeframe, since=since, until=until, limit=limit
            )
        )
        candles = normalize_candles(candles)
        validation = validate_candles(candles, timeframe=timeframe, raise_on_error=True)

        now = utc_now()
        for candle in candles:
            existing = await self.session.scalar(
                select(CandleORM).where(
                    CandleORM.symbol == candle.symbol,
                    CandleORM.timeframe == candle.timeframe,
                    CandleORM.open_time == candle.open_time,
                )
            )
            if existing is None:
                self.session.add(
                    CandleORM(
                        symbol=candle.symbol,
                        timeframe=candle.timeframe,
                        open_time=candle.open_time,
                        close_time=candle.close_time,
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        volume=candle.volume,
                        quote_volume=candle.quote_volume,
                        trade_count=candle.trade_count,
                        is_closed=candle.is_closed,
                        created_at=now,
                    )
                )
            else:
                existing.open = candle.open
                existing.high = candle.high
                existing.low = candle.low
                existing.close = candle.close
                existing.volume = candle.volume
                existing.close_time = candle.close_time
                existing.quote_volume = candle.quote_volume
                existing.trade_count = candle.trade_count
                existing.is_closed = candle.is_closed
        await self.session.commit()
        assert validation.ok
        return candles

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = 500,
    ) -> list[Candle]:
        rows = (
            await self.session.scalars(
                select(CandleORM)
                .where(CandleORM.symbol == symbol, CandleORM.timeframe == timeframe)
                .order_by(CandleORM.open_time.desc())
                .limit(limit)
            )
        ).all()
        candles = [
            Candle(
                symbol=r.symbol,
                timeframe=r.timeframe,
                open_time=r.open_time,
                close_time=r.close_time,
                open=r.open,
                high=r.high,
                low=r.low,
                close=r.close,
                volume=r.volume,
                quote_volume=r.quote_volume,
                trade_count=r.trade_count,
                is_closed=r.is_closed,
            )
            for r in reversed(rows)
        ]
        return normalize_candles(candles)
