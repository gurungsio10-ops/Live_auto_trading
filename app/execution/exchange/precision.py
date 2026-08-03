"""Symbol precision helpers for Binance spot filters (Decimal-only)."""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

from app.models.domain.market import SymbolInfo


def quantize_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Round ``value`` down to a multiple of ``step``."""
    if step <= 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def quantize_quantity(quantity: Decimal, info: SymbolInfo) -> Decimal:
    qty = quantize_to_step(quantity, info.step_size)
    if qty < info.min_quantity:
        return Decimal("0")
    return qty


def quantize_price(price: Decimal, info: SymbolInfo) -> Decimal:
    return quantize_to_step(price, info.tick_size)


def meets_min_notional(quantity: Decimal, price: Decimal, info: SymbolInfo) -> bool:
    return quantity * price >= info.min_notional
