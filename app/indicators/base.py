"""Shared indicator helpers. No look-ahead; Decimal in/out where practical."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence


class InsufficientDataError(ValueError):
    """Raised when an indicator lacks enough history."""


def ensure_length(values: Sequence, minimum: int, name: str) -> None:
    if len(values) < minimum:
        raise InsufficientDataError(
            f"{name} requires at least {minimum} values, got {len(values)}"
        )


def to_decimals(values: Sequence[Decimal | int | float | str]) -> list[Decimal]:
    return [v if isinstance(v, Decimal) else Decimal(str(v)) for v in values]


def sma_at(values: Sequence[Decimal], period: int, index: int) -> Decimal | None:
    """SMA using only data up to and including `index`."""
    if period <= 0:
        raise ValueError("period must be > 0")
    if index < period - 1 or index >= len(values):
        return None
    window = values[index - period + 1 : index + 1]
    return sum(window, Decimal("0")) / Decimal(period)
