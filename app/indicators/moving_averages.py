"""SMA, EMA, volume MA, highest-high, lowest-low."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.indicators.base import (
    InsufficientDataError,
    ensure_length,
    sma_at,
    to_decimals,
)


def sma(
    values: Sequence[Decimal | int | float | str], period: int
) -> list[Decimal | None]:
    data = to_decimals(values)
    if not data:
        raise InsufficientDataError("sma received empty input")
    ensure_length(data, 1, "sma")
    if period <= 0:
        raise ValueError("period must be > 0")
    return [sma_at(data, period, i) for i in range(len(data))]


def ema(
    values: Sequence[Decimal | int | float | str], period: int
) -> list[Decimal | None]:
    data = to_decimals(values)
    if not data:
        raise InsufficientDataError("ema received empty input")
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(data) < period:
        return [None] * len(data)

    result: list[Decimal | None] = [None] * len(data)
    seed = sum(data[:period], Decimal("0")) / Decimal(period)
    result[period - 1] = seed
    multiplier = Decimal("2") / (Decimal(period) + Decimal("1"))
    prev = seed
    for i in range(period, len(data)):
        prev = (data[i] - prev) * multiplier + prev
        result[i] = prev
    return result


def volume_ma(
    volumes: Sequence[Decimal | int | float | str], period: int
) -> list[Decimal | None]:
    return sma(volumes, period)


def highest_high(
    highs: Sequence[Decimal | int | float | str], period: int
) -> list[Decimal | None]:
    data = to_decimals(highs)
    if not data:
        raise InsufficientDataError("highest_high received empty input")
    if period <= 0:
        raise ValueError("period must be > 0")
    out: list[Decimal | None] = []
    for i in range(len(data)):
        if i < period - 1:
            out.append(None)
        else:
            out.append(max(data[i - period + 1 : i + 1]))
    return out


def lowest_low(
    lows: Sequence[Decimal | int | float | str], period: int
) -> list[Decimal | None]:
    data = to_decimals(lows)
    if not data:
        raise InsufficientDataError("lowest_low received empty input")
    if period <= 0:
        raise ValueError("period must be > 0")
    out: list[Decimal | None] = []
    for i in range(len(data)):
        if i < period - 1:
            out.append(None)
        else:
            out.append(min(data[i - period + 1 : i + 1]))
    return out
