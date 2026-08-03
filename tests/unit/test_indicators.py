"""Phase 3: indicator unit tests against hand-checked reference values."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.indicators import (
    InsufficientDataError,
    atr,
    bollinger_bands,
    ema,
    highest_high,
    lowest_low,
    macd,
    rsi,
    sma,
    volume_ma,
    vwap,
)


def _q(value: Decimal | None, places: str = "0.0001") -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def test_sma_known_values():
    values = [1, 2, 3, 4, 5]
    result = sma(values, 3)
    assert result[:2] == [None, None]
    assert result[2] == Decimal("2")
    assert result[3] == Decimal("3")
    assert result[4] == Decimal("4")


def test_ema_known_seed_and_next():
    # period=3, seed = avg(1,2,3)=2; next = (4-2)*(2/4)+2 = 3
    values = [1, 2, 3, 4]
    result = ema(values, 3)
    assert result[0] is None and result[1] is None
    assert result[2] == Decimal("2")
    assert result[3] == Decimal("3")


def test_rsi_wilder_reference():
    # Classic short series — hand-checked Wilder RSI(2)
    closes = [44, 44.5, 43.5, 44, 45, 45.5, 44.5]
    result = rsi(closes, period=2)
    assert result[0] is None and result[1] is None
    # After 2 changes from index 0->1,1->2: gains=[0.5,0], losses=[0,1]
    # avg_gain=0.25, avg_loss=0.5, rs=0.5, rsi=100-100/1.5=33.333...
    assert _q(result[2], "0.01") == Decimal("33.33")


def test_macd_structure_and_no_lookahead():
    closes = list(range(1, 50))
    result = macd(closes, fast=3, slow=6, signal_period=3)
    assert len(result.macd) == len(closes)
    # Before slow period fills, MACD must be None
    assert all(v is None for v in result.macd[:5])
    assert result.macd[5] is not None
    # Truncating future candles must not change past outputs
    truncated = macd(closes[:-5], fast=3, slow=6, signal_period=3)
    for i in range(len(truncated.macd)):
        assert truncated.macd[i] == result.macd[i]


def test_atr_and_bollinger():
    highs = [10, 12, 11, 13, 14, 15]
    lows = [8, 9, 9, 10, 11, 12]
    closes = [9, 11, 10, 12, 13, 14]
    a = atr(highs, lows, closes, period=3)
    assert a[0] is None and a[1] is None
    assert a[2] is not None
    assert a[2] > 0

    bb = bollinger_bands([1, 2, 3, 4, 5], period=3, num_std=2)
    assert bb.middle[2] == Decimal("2")
    assert bb.upper[2] > bb.middle[2] > bb.lower[2]


def test_vwap_volume_ma_hh_ll():
    highs = [10, 11, 12]
    lows = [8, 9, 10]
    closes = [9, 10, 11]
    volumes = [100, 100, 100]
    v = vwap(highs, lows, closes, volumes)
    # typical prices: 9, 10, 11 — equal volume => cumulative avg
    assert _q(v[0], "0.01") == Decimal("9.00")
    assert _q(v[2], "0.01") == Decimal("10.00")

    assert volume_ma([1, 2, 3], 2)[2] == Decimal("2.5")
    assert highest_high([1, 5, 3, 4], 3)[3] == Decimal("5")
    assert lowest_low([1, 5, 3, 4], 3)[3] == Decimal("3")


def test_empty_input_raises():
    with pytest.raises(InsufficientDataError):
        sma([], 3)
    with pytest.raises(InsufficientDataError):
        ema([], 3)
    with pytest.raises(InsufficientDataError):
        rsi([], 14)
    with pytest.raises(InsufficientDataError):
        atr([], [], [], 14)


def test_invalid_period_and_length_mismatch():
    with pytest.raises(ValueError, match="period must be > 0"):
        sma([1, 2, 3], 0)
    with pytest.raises(ValueError, match="period must be > 0"):
        ema([1, 2, 3], -1)
    with pytest.raises(ValueError, match="length mismatch"):
        atr([1, 2], [1], [1, 2], 2)
    with pytest.raises(ValueError, match="fast period must be < slow period"):
        macd([1, 2, 3, 4, 5], fast=5, slow=3)


def test_decimal_candle_inputs_stay_decimal():
    """Indicators accept Decimal OHLC (as stored in DB) and never emit float."""
    closes = [Decimal("100.5"), Decimal("101.25"), Decimal("99.75"), Decimal("102")]
    highs = [Decimal("101"), Decimal("102"), Decimal("100.5"), Decimal("103")]
    lows = [Decimal("99.5"), Decimal("100"), Decimal("98.5"), Decimal("100.5")]
    volumes = [Decimal("1.5"), Decimal("2.0"), Decimal("1.25"), Decimal("3.0")]

    for series in (
        sma(closes, 2),
        ema(closes, 2),
        rsi(closes, 2),
        atr(highs, lows, closes, 2),
        volume_ma(volumes, 2),
        highest_high(highs, 2),
        lowest_low(lows, 2),
        vwap(highs, lows, closes, volumes),
    ):
        for value in series:
            if value is not None:
                assert isinstance(value, Decimal)
                assert not isinstance(value, float)

    bb = bollinger_bands(closes, 2)
    for band in (bb.middle, bb.upper, bb.lower):
        for value in band:
            if value is not None:
                assert isinstance(value, Decimal)
