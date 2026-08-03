"""
Portfolio reconciliation: exchange balances/positions vs local state.

Runs on a configurable interval (default 30s). On mismatch:
- logs a warning
- emits an alert
- optionally repairs local snapshot from exchange (source of truth on testnet)
- flips ``reconciliation_healthy`` for the risk engine
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.time import utc_now
from app.models.domain.trading import Balance, Position
from app.monitoring.health import AlertChannel, ConsoleAlertChannel

logger = get_logger("portfolio.reconciler")


class BalanceSource(Protocol):
    async def fetch_balances(self) -> list[Balance]: ...


class LocalPortfolioView(Protocol):
    def local_balances(self) -> dict[str, Decimal]: ...

    def local_positions(self) -> dict[str, Decimal]: ...

    def apply_exchange_balances(self, balances: list[Balance]) -> None: ...

    def apply_exchange_positions(self, positions: dict[str, Decimal]) -> None: ...


@dataclass
class ReconcileReport:
    matched: bool
    balance_mismatches: list[dict[str, Any]] = field(default_factory=list)
    position_mismatches: list[dict[str, Any]] = field(default_factory=list)
    repaired: bool = False
    checked_at: str = ""
    detail: str = ""


@dataclass
class InMemoryLocalPortfolio:
    """Simple local ledger used by the testnet runtime."""

    balances: dict[str, Decimal] = field(default_factory=dict)
    positions: dict[str, Decimal] = field(default_factory=dict)

    def local_balances(self) -> dict[str, Decimal]:
        return dict(self.balances)

    def local_positions(self) -> dict[str, Decimal]:
        return dict(self.positions)

    def apply_exchange_balances(self, balances: list[Balance]) -> None:
        self.balances = {
            b.asset: (b.total if b.total is not None else b.free + b.locked)
            for b in balances
        }

    def apply_exchange_positions(self, positions: dict[str, Decimal]) -> None:
        self.positions = dict(positions)

    def seed_from_positions(self, open_positions: list[Position]) -> None:
        for p in open_positions:
            base = p.symbol.split("/")[0]
            self.positions[p.symbol] = p.quantity
            self.balances[base] = self.balances.get(base, Decimal("0")) + p.quantity


@dataclass
class PortfolioReconciler:
    exchange: BalanceSource
    local: LocalPortfolioView
    settings: Settings | None = None
    channels: list[AlertChannel] = field(
        default_factory=lambda: [ConsoleAlertChannel()]
    )
    auto_repair: bool = True
    tolerance: Decimal = Decimal("0.00000001")
    reconciliation_healthy: bool = True
    last_report: ReconcileReport | None = None
    _task: asyncio.Task | None = None
    _running: bool = False

    async def reconcile_once(self) -> ReconcileReport:
        exchange_balances = await self.exchange.fetch_balances()
        ex_map = {
            b.asset: (b.total if b.total is not None else b.free + b.locked)
            for b in exchange_balances
        }
        local_map = self.local.local_balances()
        balance_mismatches: list[dict[str, Any]] = []
        assets = set(ex_map) | set(local_map)
        for asset in sorted(assets):
            # Ignore dust on either side below tolerance.
            ev = ex_map.get(asset, Decimal("0"))
            lv = local_map.get(asset, Decimal("0"))
            if abs(ev - lv) > self.tolerance:
                balance_mismatches.append(
                    {
                        "asset": asset,
                        "exchange": str(ev),
                        "local": str(lv),
                        "delta": str(ev - lv),
                    }
                )

        # Positions: derive from base asset balances for spot (symbol BTC/USDT → BTC).
        position_mismatches: list[dict[str, Any]] = []
        local_positions = self.local.local_positions()
        for symbol, qty in local_positions.items():
            base = symbol.split("/")[0]
            ex_qty = ex_map.get(base, Decimal("0"))
            if abs(ex_qty - qty) > self.tolerance:
                position_mismatches.append(
                    {
                        "symbol": symbol,
                        "exchange_base": str(ex_qty),
                        "local": str(qty),
                    }
                )

        matched = not balance_mismatches and not position_mismatches
        repaired = False
        if not matched and self.auto_repair:
            self.local.apply_exchange_balances(exchange_balances)
            repaired_positions = {
                sym: ex_map.get(sym.split("/")[0], Decimal("0"))
                for sym in local_positions
            }
            self.local.apply_exchange_positions(repaired_positions)
            repaired = True
            logger.warning(
                "portfolio_mismatch_repaired",
                extra={
                    "balance_mismatches": len(balance_mismatches),
                    "position_mismatches": len(position_mismatches),
                },
            )
            await self._alert(
                "PORTFOLIO_MISMATCH",
                "Exchange vs local portfolio mismatch — repaired from exchange",
                {
                    "balances": balance_mismatches,
                    "positions": position_mismatches,
                },
            )

        self.reconciliation_healthy = matched or repaired
        report = ReconcileReport(
            matched=matched,
            balance_mismatches=balance_mismatches,
            position_mismatches=position_mismatches,
            repaired=repaired,
            checked_at=utc_now().isoformat(),
            detail="ok" if matched else "mismatch",
        )
        self.last_report = report
        if matched:
            logger.info("portfolio_reconcile_ok")
        return report

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        settings = self.settings or get_settings()
        interval = settings.testnet_reconcile_seconds
        while self._running:
            try:
                await self.reconcile_once()
            except Exception as exc:
                self.reconciliation_healthy = False
                logger.warning(
                    "portfolio_reconcile_error",
                    extra={"error_type": type(exc).__name__},
                )
                await self._alert(
                    "RECONCILE_FAILED",
                    f"Reconcile failed: {type(exc).__name__}",
                    {},
                )
            await asyncio.sleep(interval)

    async def _alert(self, event: str, message: str, payload: dict[str, Any]) -> None:
        for ch in self.channels:
            await ch.send(event, message, payload)
