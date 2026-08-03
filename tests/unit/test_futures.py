"""Phase 15: futures/leverage helpers (isolated margin; default cap 1x)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.core.config import Settings
from app.execution.futures import (
    FuturesContractSpec,
    funding_fee,
    liquidation_price_long,
    validate_leverage,
)


def test_default_leverage_cap_is_one() -> None:
    check = validate_leverage(Decimal("2"), entry=Decimal("100000"))
    assert check.ok is False
    assert "exceeds cap" in check.message
    assert check.liquidation_price is None


def test_settings_default_leverage_is_one() -> None:
    settings = Settings(_env_file=None)
    assert settings.default_leverage == Decimal("1")
    spec = FuturesContractSpec(
        symbol="BTC/USDT:USDT",
        maintenance_margin_rate=Decimal("0.005"),
        initial_margin_rate=Decimal("1"),
    )
    assert spec.max_leverage == Decimal("1")


def test_liquidation_and_funding() -> None:
    liq = liquidation_price_long(Decimal("100"), Decimal("1"), Decimal("0.005"))
    assert liq == Decimal("100") * Decimal("0.005")
    fee = funding_fee(Decimal("1000"), Decimal("0.0001"))
    assert fee == Decimal("0.1")
    ok = validate_leverage(
        Decimal("1"), entry=Decimal("100000"), min_liquidation_distance=Decimal("0")
    )
    assert ok.ok is True
    assert ok.liquidation_price is not None


def test_leverage_must_be_positive_for_liquidation() -> None:
    with pytest.raises(ValueError, match="leverage must be > 0"):
        liquidation_price_long(Decimal("100"), Decimal("0"), Decimal("0.005"))
    with pytest.raises(ValueError, match="leverage must be > 0"):
        liquidation_price_long(Decimal("100"), Decimal("-1"), Decimal("0.005"))


def test_validate_rejects_leverage_below_one() -> None:
    check = validate_leverage(
        Decimal("0.5"),
        entry=Decimal("100000"),
        max_leverage=Decimal("10"),
    )
    assert check.ok is False
    assert check.message == "leverage must be >= 1"
    assert check.liquidation_price is None


def test_validate_rejects_thin_liquidation_distance() -> None:
    # High leverage shrinks distance below the 5% minimum.
    check = validate_leverage(
        Decimal("20"),
        entry=Decimal("100000"),
        max_leverage=Decimal("50"),
        maintenance_rate=Decimal("0.005"),
        min_liquidation_distance=Decimal("0.05"),
    )
    assert check.ok is False
    assert check.liquidation_price is not None
    assert "liquidation distance" in check.message


def test_validate_zero_entry_fails_distance() -> None:
    check = validate_leverage(
        Decimal("1"),
        entry=Decimal("0"),
        max_leverage=Decimal("1"),
        min_liquidation_distance=Decimal("0.05"),
    )
    assert check.ok is False
    assert "liquidation distance" in check.message


def test_explicit_max_leverage_override() -> None:
    denied = validate_leverage(
        Decimal("3"), entry=Decimal("100000"), max_leverage=Decimal("2")
    )
    assert denied.ok is False
    allowed = validate_leverage(
        Decimal("2"),
        entry=Decimal("100000"),
        max_leverage=Decimal("5"),
        min_liquidation_distance=Decimal("0"),
    )
    assert allowed.ok is True


def test_futures_not_wired_into_order_paths() -> None:
    """Phase 15 primitives must remain isolated from live/paper submit paths."""
    for rel in (
        "app/execution/gateway.py",
        "app/execution/paper/engine.py",
        "app/execution/exchange/testnet.py",
        "app/risk/engine.py",
        "app/api/routes.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert "execution.futures" not in src
        assert "validate_leverage" not in src
        assert "liquidation_price_long" not in src
