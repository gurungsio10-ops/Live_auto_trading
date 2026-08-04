"""Paper portfolio reconciliation — fail closed on severe mismatches."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.time import utc_now
from app.services.paper_session import get_paper_session

logger = get_logger("reconciliation")

_STATE: dict[str, Any] = {
    "healthy": True,
    "last_run_at": None,
    "last_result": None,
}


@dataclass(frozen=True)
class ReconciliationResult:
    healthy: bool
    cash_ok: bool
    positions_ok: bool
    detail: str
    cash: str
    position_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "cash_ok": self.cash_ok,
            "positions_ok": self.positions_ok,
            "detail": self.detail,
            "cash": self.cash,
            "position_count": self.position_count,
            "checked_at": utc_now().isoformat(),
        }


def reconciliation_status() -> dict[str, Any]:
    return {
        "healthy": bool(_STATE["healthy"]),
        "last_run_at": _STATE["last_run_at"],
        "last_result": _STATE["last_result"],
    }


def is_reconciliation_healthy() -> bool:
    return bool(_STATE["healthy"])


async def run_paper_reconciliation() -> ReconciliationResult:
    """
    Recompute expected cash/equity invariants from in-memory paper engine.

    Severe negative cash or inconsistent position quantities fail closed.
    """
    settings = get_settings()
    if not settings.enable_reconciliation:
        result = ReconciliationResult(
            True, True, True, "reconciliation disabled", "0", 0
        )
        _STATE["healthy"] = True
        _STATE["last_run_at"] = utc_now().isoformat()
        _STATE["last_result"] = result.to_dict()
        return result

    session = get_paper_session()
    paper = session.paper
    cash = paper.state.cash
    cash_ok = cash >= Decimal("0")
    positions_ok = True
    for _symbol, pos in paper.state.positions.items():
        if pos.quantity < 0:
            positions_ok = False
        # Reconstruct rough notional sanity
        if pos.entry_price <= 0 or pos.current_price < 0:
            positions_ok = False

    # Rebuild cash from fills if fills exist (detect ledger drift).
    reconstructed = settings.paper_starting_balance
    for fill in paper.state.fills:
        notional = fill.quantity * fill.price
        if fill.side.value.lower() == "buy":
            reconstructed -= notional + fill.fee
        else:
            reconstructed += notional - fill.fee
    drift = abs(reconstructed - cash)
    # Allow tiny rounding drift
    drift_ok = drift <= Decimal("0.05") or len(paper.state.fills) == 0
    healthy = cash_ok and positions_ok and drift_ok
    detail = "ok"
    if not cash_ok:
        detail = "negative cash"
    elif not positions_ok:
        detail = "invalid position state"
    elif not drift_ok:
        detail = f"cash drift {drift} vs fill ledger"

    result = ReconciliationResult(
        healthy=healthy,
        cash_ok=cash_ok and drift_ok,
        positions_ok=positions_ok,
        detail=detail,
        cash=str(cash),
        position_count=len(paper.state.positions),
    )
    _STATE["healthy"] = healthy
    _STATE["last_run_at"] = utc_now().isoformat()
    _STATE["last_result"] = result.to_dict()

    # Propagate into risk engine for fail-closed order blocking.
    session.risk_engine.state.reconciliation_healthy = healthy
    logger.info(
        "reconciliation_complete",
        extra={"healthy": healthy, "detail": detail, "cash": str(cash)},
    )
    return result
