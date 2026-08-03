"""ATR, Bollinger Bands, VWAP."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from app.indicators.base import InsufficientDataError, to_decimals
from app.indicators.moving_averages import sma


def true_range(
    highs: Sequence[Decimal],
    lows: Sequence[Decimal],
    closes: Sequence[Decimal],
    index: int,
) -> Decimal:
    high = highs[index]
    low = lows[index]
    if index == 0:
        return high - low
    prev_close = closes[index - 1]
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(
    highs: Sequence[Decimal | int | float | str],
    lows: Sequence[Decimal | int | float | str],
    closes: Sequence[Decimal | int | float | str],
    period: int = 14,
) -> list[Decimal | None]:
    h = to_decimals(highs)
    l = to_decimals(lows)
    c = to_decimals(closes)
    if not h or not l or not c:
        raise InsufficientDataError("atr received empty input")
    if not (len(h) == len(l) == len(c)):
        raise ValueError("highs/lows/closes length mismatch")
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(c) < period:
        return [None] * len(c)

    trs = [true_range(h, l, c, i) for i in range(len(c))]
    out: list[Decimal | None] = [None] * len(c)
    seed = sum(trs[:period], Decimal("0")) / Decimal(period)
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(c)):
        prev = (prev * (period - 1) + trs[i]) / Decimal(period)
        out[i] = prev
    return out


@dataclass(frozen=True)
class BollingerResult:
    middle: list[Decimal | None]
    upper: list[Decimal | None]
    lower: list[Decimal | None]


def bollinger_bands(
    values: Sequence[Decimal | int | float | str],
    period: int = 20,
    num_std: Decimal | int | float | str = 2,
) -> BollingerResult:
    data = to_decimals(values)
    if not data:
        raise InsufficientDataError("bollinger_bands received empty input")
    if period <= 0:
        raise ValueError("period must be > 0")
    k = Decimal(str(num_std))
    mid = sma(data, period)
    upper: list[Decimal | None] = []
    lower: list[Decimal | None] = []
    for i in range(len(data)):
        m = mid[i]
        if m is None:
            upper.append(None)
            lower.append(None)
            continue
        window = data[i - period + 1 : i + 1]
        mean = m
        variance = sum((x - mean) ** 2 for x in window) / Decimal(period)
        std = variance.sqrt()
        upper.append(mean + k * std)
        lower.append(mean - k * std)
    return BollingerResult(middle=mid, upper=upper, lower=lower)


def vwap(
    highs: Sequence[Decimal | int | float | str],
    lows: Sequence[Decimal | int | float | str],
    closes: Sequence[Decimal | int | float | str],
    volumes: Sequence[Decimal | int | float | str],
) -> list[Decimal | None]:
    h = to_decimals(highs)
    l = to_decimals(lows)
    c = to_decimals(closes)
    v = to_decimals(volumes)
    if not h:
        raise InsufficientDataError("vwap received empty input")
    if not (len(h) == len(l) == len(c) == len(v)):
        raise ValueError("series length mismatch")

    out: list[Decimal | None] = []
    cum_pv = Decimal("0")
    cum_v = Decimal("0")
    for i in range(len(c)):
        typical = (h[i] + l[i] + c[i]) / Decimal("3")
        cum_pv += typical * v[i]
        cum_v += v[i]
        if cum_v == 0:
            out.append(None)
        else:
            out.append(cum_pv / cum_v)
    return out
