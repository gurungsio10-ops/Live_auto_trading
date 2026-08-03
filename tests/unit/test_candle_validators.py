"""Phase 2: candle validators."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.market_data.validators.candles import (
    CandleValidationError,
    validate_candles,
    validate_ohlc_sanity,
)
from tests.conftest import make_candle


def test_ohlc_sanity_detects_bad_high():
    # Bypass Candle model validator by constructing via model_construct
    from app.core.time import from_unix_ms
    from app.models.domain.market import Candle

    bad = Candle.model_construct(
        symbol="BTC/USDT",
        timeframe="1m",
        open_time=from_unix_ms(0),
        open=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("98"),
        volume=Decimal("1"),
    )
    issues = validate_ohlc_sanity(bad)
    codes = {i.code for i in issues}
    assert "OHLC_HIGH_INVALID" in codes


def test_detects_duplicates_and_missing():
    base = 1_700_000_000_000
    c0 = make_candle(base, "100", "110", "90", "105", "10")
    c1 = make_candle(base + 60_000, "105", "115", "100", "110", "12")
    # skip 2 minutes, jump to +3m
    c3 = make_candle(base + 180_000, "110", "120", "105", "115", "8")
    # duplicate of c1
    dup = make_candle(base + 60_000, "105", "115", "100", "110", "12")

    result = validate_candles([c0, c1, c3, dup], timeframe="1m")
    assert not result.ok
    codes = {i.code for i in result.issues}
    assert "DUPLICATE_CANDLE" in codes
    assert "MISSING_CANDLE" in codes
    assert len(result.missing_timestamps) == 1
    assert result.missing_timestamps[0] == c1.open_time + timedelta(minutes=1)


def test_continuous_series_passes():
    base = 1_700_000_000_000
    candles = [
        make_candle(base + i * 60_000, "100", "110", "90", "105", "1") for i in range(5)
    ]
    result = validate_candles(candles, timeframe="1m", raise_on_error=True)
    assert result.ok


def test_raise_on_error():
    base = 1_700_000_000_000
    c0 = make_candle(base, "100", "110", "90", "105", "10")
    c2 = make_candle(base + 120_000, "100", "110", "90", "105", "10")
    with pytest.raises(CandleValidationError):
        validate_candles([c0, c2], timeframe="1m", raise_on_error=True)
