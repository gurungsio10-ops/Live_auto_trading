"""
Deterministic offline sample market — a self-contained candle series used by the
CLI ``--offline`` mode (and available for demos) so the full paper-trading
pipeline can run without any network access.

The series is engineered so the EMA-trend strategy produces a genuine
BUY -> hold -> EXIT cycle (a completed paper trade), plus warm-up HOLDs.
No randomness; pure ``Decimal`` math; timezone-aware UTC timestamps.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from decimal import Decimal

from app.core.time import utc_now
from app.models.domain.market import Candle

_INTERVAL_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240}


def _entry_closes(base: Decimal) -> list[Decimal]:
    n = 60
    closes = [base * (Decimal(1) + Decimal("0.0015") * Decimal(i)) for i in range(n)]
    tail = [
        "0.004",
        "-0.006",
        "0.003",
        "-0.007",
        "0.004",
        "-0.006",
        "0.005",
        "-0.007",
        "0.004",
        "-0.006",
        "0.005",
        "-0.007",
        "0.004",
        "0.006",
    ]
    k0 = n - len(tail)
    c = closes[k0 - 1]
    for k, r in enumerate(tail):
        c = c * (Decimal(1) + Decimal(r))
        closes[k0 + k] = c
    return closes


def build_sample_candles(
    symbol: str = "BTC/USDT",
    interval: str = "1m",
    start: datetime | None = None,
    base_price: Decimal = Decimal(30000),
) -> list[Candle]:
    step = timedelta(minutes=_INTERVAL_MINUTES.get(interval, 1))
    start = start or (utc_now() - step * 90)

    closes = _entry_closes(base_price)
    last = closes[-1]
    for j in range(1, 26):  # downtrend to force EMA cross-under -> EXIT
        closes.append(last * (Decimal(1) - Decimal("0.004") * Decimal(j)))

    candles: list[Candle] = []
    prev = closes[0]
    for i, raw in enumerate(closes):
        close = raw.quantize(Decimal("0.01"))
        open_ = prev if i > 0 else (close * Decimal("0.999")).quantize(Decimal("0.01"))
        high = (max(open_, close) * Decimal("1.0015")).quantize(Decimal("0.01"))
        low = (min(open_, close) * Decimal("0.9985")).quantize(Decimal("0.01"))
        volume = Decimal(1000) + Decimal(300) * Decimal(str(abs(math.sin(i / 3.0))))
        if 46 <= i <= 59:
            volume = Decimal(4500)
        candles.append(
            Candle(
                symbol=symbol,
                timeframe=interval,
                open_time=start + step * i,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                is_closed=True,
            )
        )
        prev = close
    return candles
