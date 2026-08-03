"""Shared pytest fixtures."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force safe defaults for all tests before Settings is cached.
os.environ.setdefault("TRADING_MODE", "paper")
os.environ.setdefault("LIVE_TRADING_ENABLED", "false")
os.environ.setdefault("KILL_SWITCH_ENABLED", "false")
os.environ.setdefault("EXCHANGE_ENV", "paper")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.core.config import get_settings
from app.db.base import Base
from app.models.domain.market import Candle
from app.core.time import from_unix_ms


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def make_candle(
    open_ms: int,
    o: str,
    h: str,
    l: str,
    c: str,
    v: str,
    *,
    symbol: str = "BTC/USDT",
    timeframe: str = "1m",
) -> Candle:
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        open_time=from_unix_ms(open_ms),
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
        volume=Decimal(v),
    )
