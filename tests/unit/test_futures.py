"""Phase 15: futures/leverage helpers (default cap 1x)."""

from __future__ import annotations

from decimal import Decimal

from app.execution.futures import funding_fee, liquidation_price_long, validate_leverage


def test_default_leverage_cap_is_one():
    check = validate_leverage(Decimal("2"), entry=Decimal("100000"))
    assert check.ok is False


def test_liquidation_and_funding():
    liq = liquidation_price_long(Decimal("100"), Decimal("1"), Decimal("0.005"))
    assert liq > 0
    fee = funding_fee(Decimal("1000"), Decimal("0.0001"))
    assert fee == Decimal("0.1")
    ok = validate_leverage(Decimal("1"), entry=Decimal("100000"), min_liquidation_distance=Decimal("0"))
    assert ok.ok is True
