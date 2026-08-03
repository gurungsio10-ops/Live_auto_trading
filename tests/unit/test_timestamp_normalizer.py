"""Phase 2: timestamp normalization to UTC."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from app.market_data.normalizers.timestamps import normalize_candle_timestamps
from app.models.domain.market import Candle


def test_naive_timestamp_becomes_utc():
    candle = Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=datetime(2024, 1, 1, 12, 0, 0),
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("1"),
        close=Decimal("1.5"),
        volume=Decimal("10"),
    )
    normalized = normalize_candle_timestamps(candle)
    assert normalized.open_time.tzinfo == UTC


def test_offset_timestamp_converted_to_utc():
    eastern = timezone(timedelta(hours=-5))
    candle = Candle(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=datetime(2024, 1, 1, 7, 0, 0, tzinfo=eastern),
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("1"),
        close=Decimal("1.5"),
        volume=Decimal("10"),
    )
    normalized = normalize_candle_timestamps(candle)
    assert normalized.open_time == datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
