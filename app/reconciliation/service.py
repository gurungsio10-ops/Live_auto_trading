"""Compare exchange-reported state against recorded local state.

Fail-closed: until a comparison completes successfully with no mismatches,
``healthy`` is False. Missing sources or fetch errors are unhealthy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class AssetBalance:
    asset: str
    total: Decimal


@dataclass(frozen=True)
class PositionQty:
    symbol: str
    quantity: Decimal


@dataclass(frozen=True)
class ExchangeSnapshot:
    balances: tuple[AssetBalance, ...]
    positions: tuple[PositionQty, ...]


@dataclass(frozen=True)
class LocalSnapshot:
    balances: tuple[AssetBalance, ...]
    positions: tuple[PositionQty, ...]


@dataclass(frozen=True)
class ReconciliationResult:
    ok: bool
    completed: bool
    balances_verified: bool
    message: str
    mismatches: tuple[str, ...] = ()


class ExchangeStateSource(Protocol):
    def fetch_snapshot(self) -> ExchangeSnapshot: ...


class LocalStateSource(Protocol):
    def fetch_snapshot(self) -> LocalSnapshot: ...


@dataclass
class InMemoryExchangeState:
    """Stub/testnet exchange state source."""

    balances: tuple[AssetBalance, ...] = ()
    positions: tuple[PositionQty, ...] = ()
    fail: bool = False

    def fetch_snapshot(self) -> ExchangeSnapshot:
        if self.fail:
            raise RuntimeError("exchange state unavailable")
        return ExchangeSnapshot(balances=self.balances, positions=self.positions)


@dataclass
class InMemoryLocalState:
    """Recorded local balances/positions for comparison."""

    balances: tuple[AssetBalance, ...] = ()
    positions: tuple[PositionQty, ...] = ()
    fail: bool = False

    def fetch_snapshot(self) -> LocalSnapshot:
        if self.fail:
            raise RuntimeError("local state unavailable")
        return LocalSnapshot(balances=self.balances, positions=self.positions)


def _balance_map(items: tuple[AssetBalance, ...]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for item in items:
        out[item.asset] = out.get(item.asset, Decimal("0")) + item.total
    return out


def _position_map(items: tuple[PositionQty, ...]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for item in items:
        out[item.symbol] = out.get(item.symbol, Decimal("0")) + item.quantity
    return out


class ReconciliationService:
    """
    Produces reconciliation health by comparing exchange vs local snapshots.

    Defaults to unhealthy until ``run()`` completes a successful match.
    """

    def __init__(
        self,
        exchange: ExchangeStateSource | None = None,
        local: LocalStateSource | None = None,
        *,
        tolerance: Decimal = Decimal("0"),
    ) -> None:
        self.exchange = exchange
        self.local = local
        self.tolerance = tolerance
        self._last: ReconciliationResult | None = None

    @property
    def healthy(self) -> bool:
        if self._last is None or not self._last.completed:
            return False
        return self._last.ok

    @property
    def balances_verified(self) -> bool:
        return bool(self._last and self._last.balances_verified)

    @property
    def last_result(self) -> ReconciliationResult | None:
        return self._last

    def run(self) -> ReconciliationResult:
        if self.exchange is None or self.local is None:
            result = ReconciliationResult(
                ok=False,
                completed=False,
                balances_verified=False,
                message="reconciliation sources missing",
                mismatches=("sources_missing",),
            )
            self._last = result
            return result
        try:
            exchange_snap = self.exchange.fetch_snapshot()
            local_snap = self.local.fetch_snapshot()
        except Exception as exc:
            result = ReconciliationResult(
                ok=False,
                completed=False,
                balances_verified=False,
                message=f"reconciliation incomplete: {exc}",
                mismatches=("fetch_failed",),
            )
            self._last = result
            return result

        mismatches = _diff_snapshots(exchange_snap, local_snap, self.tolerance)
        ok = not mismatches
        result = ReconciliationResult(
            ok=ok,
            completed=True,
            balances_verified=ok,
            message="ok" if ok else "state mismatch",
            mismatches=tuple(mismatches),
        )
        self._last = result
        return result


def _diff_snapshots(
    exchange: ExchangeSnapshot,
    local: LocalSnapshot,
    tolerance: Decimal,
) -> list[str]:
    mismatches: list[str] = []
    ex_bal = _balance_map(exchange.balances)
    loc_bal = _balance_map(local.balances)
    for asset in sorted(set(ex_bal) | set(loc_bal)):
        left = ex_bal.get(asset, Decimal("0"))
        right = loc_bal.get(asset, Decimal("0"))
        if abs(left - right) > tolerance:
            mismatches.append(f"balance:{asset}")
    ex_pos = _position_map(exchange.positions)
    loc_pos = _position_map(local.positions)
    for symbol in sorted(set(ex_pos) | set(loc_pos)):
        left = ex_pos.get(symbol, Decimal("0"))
        right = loc_pos.get(symbol, Decimal("0"))
        if abs(left - right) > tolerance:
            mismatches.append(f"position:{symbol}")
    return mismatches
