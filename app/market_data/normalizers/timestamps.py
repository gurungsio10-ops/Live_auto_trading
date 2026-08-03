"""Normalize candle timestamps to UTC."""

from __future__ import annotations

from app.core.time import ensure_utc
from app.models.domain.market import Candle


def normalize_candle_timestamps(candle: Candle) -> Candle:
    data = candle.model_dump()
    data["open_time"] = ensure_utc(candle.open_time)
    if candle.close_time is not None:
        data["close_time"] = ensure_utc(candle.close_time)
    return Candle.model_validate(data)


def normalize_candles(candles: list[Candle]) -> list[Candle]:
    return [normalize_candle_timestamps(c) for c in candles]
