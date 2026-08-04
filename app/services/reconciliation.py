"""Paper portfolio reconciliation — fail closed on severe mismatches."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.time import utc_now
from app.services.paper_session import get_paper_session

logger = get_logger("reconciliation")

_STATE: dict[str, Any] = {
    "healthy": True,
    "halted": False,
    "last_run_at": None,
    "last_result": None,
}


@dataclass(frozen=True)
class Mismatch:
    field: str
    expected: str
    observed: str
    difference: str
    severity: str  # critical | high | medium | low


@dataclass(frozen=True)
class ReconciliationResult:
    healthy: bool
    cash_ok: bool
    positions_ok: bool
    detail: str
    cash: str
    position_count: int
    mismatches: list[Mismatch] = field(default_factory=list)
    equity: str = "0"
    reconstructed_cash: str = "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "cash_ok": self.cash_ok,
            "positions_ok": self.positions_ok,
            "detail": self.detail,
            "cash": self.cash,
            "equity": self.equity,
            "reconstructed_cash": self.reconstructed_cash,
            "position_count": self.position_count,
            "mismatches": [
                {
                    "field": m.field,
                    "expected": m.expected,
                    "observed": m.observed,
                    "difference": m.difference,
                    "severity": m.severity,
                }
                for m in self.mismatches
            ],
            "checked_at": utc_now().isoformat(),
            "halted": bool(_STATE["halted"]),
        }


def reconciliation_status() -> dict[str, Any]:
    return {
        "healthy": bool(_STATE["healthy"]),
        "halted": bool(_STATE["halted"]),
        "last_run_at": _STATE["last_run_at"],
        "last_result": _STATE["last_result"],
    }


def is_reconciliation_healthy() -> bool:
    return bool(_STATE["healthy"]) and not bool(_STATE["halted"])


def clear_reconciliation_halt() -> None:
    """Operator-cleared halt after corrective action (does not rewrite balances)."""
    _STATE["halted"] = False
    _STATE["healthy"] = True
    session = get_paper_session()
    session.risk_engine.state.reconciliation_healthy = True


async def run_paper_reconciliation(*, persist: bool = True) -> ReconciliationResult:
    """
    Recompute expected cash/equity invariants from the paper engine ledger.

    Severe negative cash, invalid positions, or fill-ledger drift fail closed
    and activate a reconciliation halt (no silent overwrite).
    """
    settings = get_settings()
    if not settings.enable_reconciliation:
        result = ReconciliationResult(
            True, True, True, "reconciliation disabled", "0", 0
        )
        _STATE["healthy"] = True
        _STATE["halted"] = False
        _STATE["last_run_at"] = utc_now().isoformat()
        _STATE["last_result"] = result.to_dict()
        return result

    session = get_paper_session()
    paper = session.paper
    cash = paper.state.cash
    mismatches: list[Mismatch] = []
    cash_ok = cash >= Decimal("0")
    if not cash_ok:
        mismatches.append(
            Mismatch(
                field="cash",
                expected=">=0",
                observed=str(cash),
                difference=str(cash),
                severity="critical",
            )
        )

    positions_ok = True
    for symbol, pos in paper.state.positions.items():
        if pos.quantity < 0:
            positions_ok = False
            mismatches.append(
                Mismatch(
                    field=f"position.{symbol}.quantity",
                    expected=">=0",
                    observed=str(pos.quantity),
                    difference=str(pos.quantity),
                    severity="critical",
                )
            )
        if pos.entry_price <= 0 or pos.current_price < 0:
            positions_ok = False
            mismatches.append(
                Mismatch(
                    field=f"position.{symbol}.price",
                    expected=">0 entry, >=0 mark",
                    observed=f"entry={pos.entry_price} mark={pos.current_price}",
                    difference="invalid",
                    severity="critical",
                )
            )

    # Rebuild cash from fills if the fill ledger explains open positions.
    # Incomplete ledgers (e.g. hydrated positions without matching fills) must
    # not invent a false critical halt via starting-balance reconstruction.
    reconstructed = settings.paper_starting_balance
    net_qty: dict[str, Decimal] = {}
    for fill in paper.state.fills:
        notional = fill.quantity * fill.price
        side = fill.side.value.lower()
        if side == "buy":
            reconstructed -= notional + fill.fee
            net_qty[fill.symbol] = (
                net_qty.get(fill.symbol, Decimal("0")) + fill.quantity
            )
        else:
            reconstructed += notional - fill.fee
            net_qty[fill.symbol] = (
                net_qty.get(fill.symbol, Decimal("0")) - fill.quantity
            )

    ledger_complete = True
    for symbol, pos in paper.state.positions.items():
        explained = net_qty.get(symbol, Decimal("0"))
        if abs(explained - pos.quantity) > Decimal("0.00000001"):
            ledger_complete = False
            mismatches.append(
                Mismatch(
                    field=f"position.{symbol}.vs_fills",
                    expected=str(pos.quantity),
                    observed=str(explained),
                    difference=str(pos.quantity - explained),
                    severity="high",
                )
            )
    for symbol, qty in net_qty.items():
        if qty > 0 and symbol not in paper.state.positions:
            ledger_complete = False

    drift = abs(reconstructed - cash)
    if len(paper.state.fills) == 0:
        drift_ok = True
        reconstructed = cash
    elif not ledger_complete:
        # Incomplete fill history — do not fail-closed on naive reconstruction.
        drift_ok = True
    else:
        drift_ok = drift <= Decimal("0.05")
        if not drift_ok:
            mismatches.append(
                Mismatch(
                    field="cash_vs_fill_ledger",
                    expected=str(reconstructed),
                    observed=str(cash),
                    difference=str(drift),
                    severity="critical",
                )
            )

    # Equity invariant: cash + marked positions ≈ equity (tolerance).
    marked = sum(
        (p.quantity * p.current_price for p in paper.state.positions.values()),
        Decimal("0"),
    )
    equity = cash + marked
    # Fill quantity cannot exceed order quantity.
    for order in paper.state.orders.values():
        filled_qty = sum(
            (f.quantity for f in paper.state.fills if f.order_id == order.id),
            Decimal("0"),
        )
        if filled_qty > order.quantity:
            positions_ok = False
            mismatches.append(
                Mismatch(
                    field=f"order.{order.id}.filled_qty",
                    expected=f"<={order.quantity}",
                    observed=str(filled_qty),
                    difference=str(filled_qty - order.quantity),
                    severity="critical",
                )
            )

    # Halt only on critical invariant breaks (cash/positions/fill qty/drift when complete).
    healthy = (
        cash_ok
        and positions_ok
        and drift_ok
        and not any(m.severity == "critical" for m in mismatches)
    )
    detail = "ok"
    if not healthy:
        detail = next(
            (m.field for m in mismatches if m.severity == "critical"),
            mismatches[0].field if mismatches else "reconciliation_failed",
        )
        if not cash_ok:
            detail = "negative cash"
        elif not positions_ok:
            detail = "invalid position or fill state"
        elif not drift_ok:
            detail = f"cash drift {drift} vs fill ledger"
    elif mismatches:
        detail = "ok_with_warnings"

    result = ReconciliationResult(
        healthy=healthy,
        cash_ok=cash_ok and drift_ok,
        positions_ok=positions_ok,
        detail=detail,
        cash=str(cash),
        position_count=len(paper.state.positions),
        mismatches=mismatches,
        equity=str(equity),
        reconstructed_cash=str(reconstructed),
    )
    _STATE["healthy"] = healthy
    _STATE["halted"] = not healthy
    _STATE["last_run_at"] = utc_now().isoformat()
    _STATE["last_result"] = result.to_dict()

    # Propagate into risk engine for fail-closed order blocking.
    session.risk_engine.state.reconciliation_healthy = healthy
    logger.info(
        "reconciliation_complete",
        extra={"healthy": healthy, "detail": detail, "cash": str(cash)},
    )

    if persist:
        try:
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

            from app.db.base import create_engine
            from app.services import paper_persistence as store
            from app.services.cycle_lock import save_reconciliation_report

            engine = create_engine()
            factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
            async with factory() as db:
                await save_reconciliation_report(
                    db,
                    healthy=healthy,
                    detail=detail,
                    cash=str(cash),
                    position_count=len(paper.state.positions),
                    payload=result.to_dict(),
                )
                await store.save_reconciliation_halt(
                    db, halted=not healthy, detail=detail
                )
                await store.append_audit_event(
                    db,
                    event_type="RECONCILIATION",
                    message=detail,
                    severity="critical" if not healthy else "info",
                    payload={"healthy": healthy, "mismatches": len(mismatches)},
                )
            await engine.dispose()
        except Exception:
            logger.warning("reconciliation_persist_failed")

    return result
