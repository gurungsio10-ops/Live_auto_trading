"""UTC timestamp helpers. All timestamps in Atlas are UTC."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_unix_ms(dt: datetime) -> int:
    return int(ensure_utc(dt).timestamp() * 1000)


def from_unix_ms(ms: int | float) -> datetime:
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=UTC)
