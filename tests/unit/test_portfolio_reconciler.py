"""Portfolio reconciler tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.domain.trading import Balance
from app.monitoring.health import ConsoleAlertChannel
from app.services.portfolio_reconciler import (
    InMemoryLocalPortfolio,
    PortfolioReconciler,
)


class FakeExchange:
    def __init__(self, balances: list[Balance]) -> None:
        self._balances = balances

    async def fetch_balances(self) -> list[Balance]:
        return list(self._balances)


@pytest.mark.asyncio
async def test_reconcile_match():
    local = InMemoryLocalPortfolio(
        balances={"USDT": Decimal("1000"), "BTC": Decimal("0.1")}
    )
    ex = FakeExchange(
        [
            Balance(
                asset="USDT",
                free=Decimal("1000"),
                locked=Decimal("0"),
                total=Decimal("1000"),
            ),
            Balance(
                asset="BTC",
                free=Decimal("0.1"),
                locked=Decimal("0"),
                total=Decimal("0.1"),
            ),
        ]
    )
    channel = ConsoleAlertChannel()
    rec = PortfolioReconciler(
        exchange=ex, local=local, channels=[channel], auto_repair=True
    )
    report = await rec.reconcile_once()
    assert report.matched is True
    assert channel.sent == []


@pytest.mark.asyncio
async def test_reconcile_mismatch_repairs():
    local = InMemoryLocalPortfolio(
        balances={"USDT": Decimal("900")},
        positions={"BTC/USDT": Decimal("0.2")},
    )
    ex = FakeExchange(
        [
            Balance(
                asset="USDT",
                free=Decimal("1000"),
                locked=Decimal("0"),
                total=Decimal("1000"),
            ),
            Balance(
                asset="BTC",
                free=Decimal("0.1"),
                locked=Decimal("0"),
                total=Decimal("0.1"),
            ),
        ]
    )
    channel = ConsoleAlertChannel()
    rec = PortfolioReconciler(
        exchange=ex, local=local, channels=[channel], auto_repair=True
    )
    report = await rec.reconcile_once()
    assert report.matched is False
    assert report.repaired is True
    assert local.balances["USDT"] == Decimal("1000")
    assert any(a["event"] == "PORTFOLIO_MISMATCH" for a in channel.sent)
