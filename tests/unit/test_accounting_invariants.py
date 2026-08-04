"""Accounting invariant unit tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.accounting.invariants import (
    AccountingInvariantError,
    assert_cycle_invariants,
    check_cycle_invariants,
    equity_from_cash_and_positions,
)
from app.core.time import utc_now
from app.models.domain.trading import Position


def _pos(qty: str, entry: str, mark: str) -> Position:
    q = Decimal(qty)
    e = Decimal(entry)
    m = Decimal(mark)
    return Position(
        symbol="BTC/USDT",
        quantity=q,
        entry_price=e,
        current_price=m,
        unrealized_pnl=(m - e) * q,
        opened_at=utc_now(),
    )


def test_equity_identity():
    positions = {"BTC/USDT": _pos("1", "100", "110")}
    equity, marked = equity_from_cash_and_positions(Decimal("50"), positions)
    assert marked == Decimal("110")
    assert equity == Decimal("160")
    report = check_cycle_invariants(
        cash=Decimal("50"),
        positions=positions,
        realized_pnl=Decimal("0"),
        fills=[],
    )
    assert report.ok
    assert report.equity == Decimal("160")


def test_negative_cash_and_position_fail():
    report = check_cycle_invariants(
        cash=Decimal("-1"),
        positions={"BTC/USDT": _pos("-0.5", "100", "100")},
        realized_pnl=Decimal("0"),
        fills=[],
    )
    assert report.ok is False
    codes = {v.code for v in report.violations}
    assert "NEGATIVE_CASH" in codes
    assert "NEGATIVE_POSITION" in codes
    with pytest.raises(AccountingInvariantError):
        assert_cycle_invariants(
            cash=Decimal("-1"),
            positions={},
            realized_pnl=Decimal("0"),
            fills=[],
        )


def test_duplicate_fill_detected():
    class F:
        def __init__(self, id_: str, fee: str = "0.1"):
            self.id = id_
            self.fee = Decimal(fee)

    report = check_cycle_invariants(
        cash=Decimal("100"),
        positions={},
        realized_pnl=Decimal("0"),
        fills=[F("a"), F("a")],
    )
    assert any(v.code == "DUPLICATE_FILL" for v in report.violations)


def test_double_exit_pair_detected():
    class FakeOrder:
        def __init__(self, id_: str, pair: str):
            self.id = id_
            self.status = type("S", (), {"value": "FILLED"})()
            self.filled_quantity = Decimal("1")
            self.metadata = {"exit_pair_id": pair}

    report = check_cycle_invariants(
        cash=Decimal("100"),
        positions={},
        realized_pnl=Decimal("0"),
        fills=[],
        orders={
            "a": FakeOrder("a", "pair-1"),
            "b": FakeOrder("b", "pair-1"),
        },
    )
    assert any(v.code == "DOUBLE_EXIT" for v in report.violations)


def test_negative_price_detected():
    bad = _pos("1", "100", "100")
    bad = bad.model_copy(update={"current_price": Decimal("-1")})
    report = check_cycle_invariants(
        cash=Decimal("100"),
        positions={"BTC/USDT": bad},
        realized_pnl=Decimal("0"),
        fills=[],
    )
    assert any(v.code == "NEGATIVE_PRICE" for v in report.violations)
