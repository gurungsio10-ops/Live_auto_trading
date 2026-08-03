"""RSI and MACD indicators — no look-ahead."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.indicators.base import InsufficientDataError, to_decimals
from app.indicators.moving_averages import ema


def rsi(
    values: Sequence[Decimal | int | float | str], period: int = 14
) -> list[Decimal | None]:
    data = to_decimals(values)
    if not data:
        raise InsufficientDataError("rsi received empty input")
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(data) < period + 1:
        return [None] * len(data)

    out: list[Decimal | None] = [None] * len(data)
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for i in range(1, len(data)):
        change = data[i] - data[i - 1]
        gains.append(change if change > 0 else Decimal("0"))
        losses.append(-change if change < 0 else Decimal("0"))

    avg_gain = sum(gains[:period], Decimal("0")) / Decimal(period)
    avg_loss = sum(losses[:period], Decimal("0")) / Decimal(period)

    def _rsi(ag: Decimal, al: Decimal) -> Decimal:
        if al == 0:
            return Decimal("100")
        rs = ag / al
        return Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / Decimal(period)
        avg_loss = (avg_loss * (period - 1) + losses[i]) / Decimal(period)
        out[i + 1] = _rsi(avg_gain, avg_loss)
    return out


@dataclass(frozen=True)
class MACDResult:
    macd: list[Decimal | None]
    signal: list[Decimal | None]
    histogram: list[Decimal | None]


def macd(
    values: Sequence[Decimal | int | float | str],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> MACDResult:
    data = to_decimals(values)
    if not data:
        raise InsufficientDataError("macd received empty input")
    if min(fast, slow, signal_period) <= 0:
        raise ValueError("periods must be > 0")
    if fast >= slow:
        raise ValueError("fast period must be < slow period")

    fast_ema = ema(data, fast)
    slow_ema = ema(data, slow)
    macd_line: list[Decimal | None] = []
    for f, s in zip(fast_ema, slow_ema):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)

    # Signal EMA over non-None MACD values, aligned to original index.
    first_valid = next((i for i, v in enumerate(macd_line) if v is not None), None)
    signal_line: list[Decimal | None] = [None] * len(data)
    hist: list[Decimal | None] = [None] * len(data)
    if first_valid is None:
        return MACDResult(macd=macd_line, signal=signal_line, histogram=hist)

    macd_vals = [v for v in macd_line[first_valid:] if v is not None]
    # Continuity: once MACD starts it should stay non-None
    signal_vals = ema(macd_vals, signal_period)
    for offset, sig in enumerate(signal_vals):
        idx = first_valid + offset
        signal_line[idx] = sig
        macd_v = macd_line[idx]
        if sig is not None and macd_v is not None:
            hist[idx] = macd_v - sig
    return MACDResult(macd=macd_line, signal=signal_line, histogram=hist)
