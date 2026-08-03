"""Phase 15 — futures/leverage primitives (isolated margin only; default max 1x)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.config import get_settings


@dataclass(frozen=True)
class FuturesContractSpec:
    symbol: str
    maintenance_margin_rate: Decimal
    initial_margin_rate: Decimal
    max_leverage: Decimal = Decimal("1")


@dataclass(frozen=True)
class LeverageCheck:
    ok: bool
    leverage: Decimal
    liquidation_price: Decimal | None
    message: str = ""


def liquidation_price_long(
    entry: Decimal, leverage: Decimal, maintenance_rate: Decimal
) -> Decimal:
    """Isolated long approximate liquidation price."""
    if leverage <= 0:
        raise ValueError("leverage must be > 0")
    # liq ≈ entry * (1 - 1/leverage + maintenance_rate)
    return entry * (Decimal("1") - (Decimal("1") / leverage) + maintenance_rate)


def validate_leverage(
    requested: Decimal,
    *,
    entry: Decimal,
    max_leverage: Decimal | None = None,
    maintenance_rate: Decimal = Decimal("0.005"),
    min_liquidation_distance: Decimal = Decimal("0.05"),
) -> LeverageCheck:
    settings = get_settings()
    cap = max_leverage if max_leverage is not None else settings.default_leverage
    if requested > cap:
        return LeverageCheck(False, requested, None, f"leverage exceeds cap {cap}")
    if requested < 1:
        return LeverageCheck(False, requested, None, "leverage must be >= 1")
    liq = liquidation_price_long(entry, requested, maintenance_rate)
    distance = (entry - liq) / entry if entry > 0 else Decimal("0")
    if distance < min_liquidation_distance:
        return LeverageCheck(
            False, requested, liq, "liquidation distance below minimum"
        )
    return LeverageCheck(True, requested, liq, "ok")


def funding_fee(notional: Decimal, funding_rate: Decimal) -> Decimal:
    return notional * funding_rate
