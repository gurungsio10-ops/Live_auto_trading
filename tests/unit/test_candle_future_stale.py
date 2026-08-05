"""Extra candle validation cases: future timestamps and stale tips."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.core.time import utc_now
from app.market_data.validators.candles import validate_candles
from app.models.domain.market import Candle


def _c(open_time, *, symbol="BTC/USDT", timeframe="1m"):
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        open_time=open_time,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("1"),
        is_closed=True,
    )


def test_future_timestamp_rejected():
    future = utc_now() + timedelta(hours=1)
    result = validate_candles([_c(future)], timeframe="1m")
    assert result.ok is False
    assert any(i.code == "FUTURE_TIMESTAMP" for i in result.issues)


def test_stale_tip_opt_in():
    old = utc_now() - timedelta(hours=2)
    result = validate_candles([_c(old)], timeframe="1m", check_stale=True)
    assert any(i.code == "STALE_MARKET_DATA" for i in result.issues)


def test_stale_not_checked_by_default():
    old = utc_now() - timedelta(hours=2)
    result = validate_candles([_c(old)], timeframe="1m")
    assert not any(i.code == "STALE_MARKET_DATA" for i in result.issues)
