"""Reconciliation health producer — fail-closed compare of exchange vs local."""

from __future__ import annotations

from decimal import Decimal

from app.reconciliation import (
    AssetBalance,
    InMemoryExchangeState,
    InMemoryLocalState,
    PositionQty,
    ReconciliationService,
)


def test_defaults_unhealthy_until_successful_run() -> None:
    svc = ReconciliationService()
    assert svc.healthy is False
    assert svc.balances_verified is False
    result = svc.run()
    assert result.completed is False
    assert result.ok is False
    assert svc.healthy is False


def test_match_marks_healthy() -> None:
    balances = (AssetBalance("USDT", Decimal("1000")),)
    positions = (PositionQty("BTC/USDT", Decimal("0.01")),)
    svc = ReconciliationService(
        InMemoryExchangeState(balances=balances, positions=positions),
        InMemoryLocalState(balances=balances, positions=positions),
    )
    result = svc.run()
    assert result.completed is True
    assert result.ok is True
    assert result.balances_verified is True
    assert svc.healthy is True


def test_mismatch_completes_but_unhealthy() -> None:
    svc = ReconciliationService(
        InMemoryExchangeState(
            balances=(AssetBalance("USDT", Decimal("1000")),),
        ),
        InMemoryLocalState(
            balances=(AssetBalance("USDT", Decimal("900")),),
        ),
    )
    result = svc.run()
    assert result.completed is True
    assert result.ok is False
    assert "balance:USDT" in result.mismatches
    assert svc.healthy is False


def test_fetch_error_fail_closed() -> None:
    svc = ReconciliationService(
        InMemoryExchangeState(fail=True),
        InMemoryLocalState(balances=()),
    )
    result = svc.run()
    assert result.completed is False
    assert result.ok is False
    assert svc.healthy is False


def test_position_mismatch() -> None:
    svc = ReconciliationService(
        InMemoryExchangeState(
            positions=(PositionQty("BTC/USDT", Decimal("1")),),
        ),
        InMemoryLocalState(
            positions=(PositionQty("BTC/USDT", Decimal("2")),),
        ),
    )
    result = svc.run()
    assert result.ok is False
    assert "position:BTC/USDT" in result.mismatches


def test_local_fetch_error_fail_closed() -> None:
    svc = ReconciliationService(
        InMemoryExchangeState(balances=()),
        InMemoryLocalState(fail=True),
    )
    result = svc.run()
    assert result.completed is False
    assert svc.healthy is False
