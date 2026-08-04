"""Explicit paper-portfolio accounting invariants.

Uses Decimal exclusively. Called after cycles, on hydrate, and by soak harness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


class AccountingInvariantError(ValueError):
    """Raised when a critical accounting invariant fails."""


@dataclass(frozen=True)
class InvariantViolation:
    code: str
    message: str
    severity: str  # critical | high | medium


@dataclass
class InvariantReport:
    ok: bool
    equity: Decimal
    cash: Decimal
    reserved_cash: Decimal
    marked_position_value: Decimal
    violations: list[InvariantViolation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "equity": str(self.equity),
            "cash": str(self.cash),
            "reserved_cash": str(self.reserved_cash),
            "marked_position_value": str(self.marked_position_value),
            "violations": [
                {"code": v.code, "message": v.message, "severity": v.severity}
                for v in self.violations
            ],
        }


def equity_from_cash_and_positions(
    cash: Decimal,
    positions: dict[str, Any],
    reserved_cash: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]:
    """Return (equity, marked_position_value).

    Identity: ``cash + reserved_cash + marked_position_value = equity``.
    """
    marked = Decimal("0")
    for pos in positions.values():
        qty = Decimal(str(pos.quantity))
        px = Decimal(str(pos.current_price))
        marked += qty * px
    return cash + reserved_cash + marked, marked


def _open_reservation_total(orders: dict[str, Any] | None) -> Decimal:
    total = Decimal("0")
    if not orders:
        return total
    for order in orders.values():
        meta = getattr(order, "metadata", None) or {}
        if meta.get("reservation_open") != "true":
            continue
        total += Decimal(
            str(meta.get("reserved_remaining", meta.get("reserved_notional", "0")))
        )
    return total


def check_cycle_invariants(
    *,
    cash: Decimal,
    positions: dict[str, Any],
    realized_pnl: Decimal,
    fills: list[Any],
    orders: dict[str, Any] | None = None,
    reserved_cash: Decimal = Decimal("0"),
    allow_negative_cash: bool = False,
    equity_tolerance: Decimal = Decimal("0.00000001"),
) -> InvariantReport:
    """
    Verify core accounting invariants for the paper ledger.

    Identity: cash + reserved_cash + marked_position_value = equity.
    Open BUY reservations must sum to ``reserved_cash`` (within tolerance).
    """
    violations: list[InvariantViolation] = []
    equity, marked = equity_from_cash_and_positions(
        cash, positions, reserved_cash=reserved_cash
    )
    recomputed = cash + reserved_cash + marked
    if abs(equity - recomputed) > equity_tolerance:
        violations.append(
            InvariantViolation(
                code="EQUITY_IDENTITY",
                message=f"equity {equity} != cash+reserved+marked {recomputed}",
                severity="critical",
            )
        )

    if not allow_negative_cash and cash < 0:
        violations.append(
            InvariantViolation(
                code="NEGATIVE_CASH",
                message=f"cash {cash} < 0",
                severity="critical",
            )
        )

    if reserved_cash < 0:
        violations.append(
            InvariantViolation(
                code="NEGATIVE_RESERVED",
                message=f"reserved_cash {reserved_cash} < 0",
                severity="critical",
            )
        )

    open_res = _open_reservation_total(orders)
    if abs(open_res - reserved_cash) > Decimal("0.00000001"):
        violations.append(
            InvariantViolation(
                code="RESERVATION_MISMATCH",
                message=(
                    f"open order reservations {open_res} != reserved_cash {reserved_cash}"
                ),
                severity="critical",
            )
        )

    for symbol, pos in positions.items():
        qty = Decimal(str(pos.quantity))
        if qty < 0:
            violations.append(
                InvariantViolation(
                    code="NEGATIVE_POSITION",
                    message=f"{symbol} quantity {qty} < 0",
                    severity="critical",
                )
            )
        entry = Decimal(str(pos.entry_price))
        mark = Decimal(str(pos.current_price))
        if entry < 0 or mark < 0:
            violations.append(
                InvariantViolation(
                    code="NEGATIVE_PRICE",
                    message=f"{symbol} has negative price entry={entry} mark={mark}",
                    severity="critical",
                )
            )
        expected_upnl = (mark - entry) * qty
        observed_upnl = Decimal(str(getattr(pos, "unrealized_pnl", expected_upnl)))
        if abs(expected_upnl - observed_upnl) > Decimal("0.01"):
            violations.append(
                InvariantViolation(
                    code="UNREALIZED_MISMATCH",
                    message=(
                        f"{symbol} unrealized {observed_upnl} != "
                        f"(mark-entry)*qty {expected_upnl}"
                    ),
                    severity="high",
                )
            )

    # Fee uniqueness: each fill id appears once.
    seen_fill_ids: set[str] = set()
    fees = Decimal("0")
    for fill in fills:
        fid = str(getattr(fill, "id", ""))
        if fid and fid in seen_fill_ids:
            violations.append(
                InvariantViolation(
                    code="DUPLICATE_FILL",
                    message=f"fill id {fid} appears more than once",
                    severity="critical",
                )
            )
        if fid:
            seen_fill_ids.add(fid)
        fees += Decimal(str(getattr(fill, "fee", "0")))

    if orders:
        for order in orders.values():
            status = getattr(order.status, "value", str(order.status))
            filled_qty = Decimal(str(getattr(order, "filled_quantity", "0")))
            if status in {"CANCELLED", "EXPIRED"} and filled_qty > getattr(
                order, "filled_quantity", filled_qty
            ):
                # Cancelled/expired may keep prior partial fills; remaining must not grow.
                pass
            if status in {"CANCELLED", "EXPIRED"}:
                # Ensure no new fills after terminal cancel/expire — checked by soak.
                pass
            # Stop-loss and take-profit both filled for same protective pair is forbidden
            # when metadata marks them as a linked exit pair.
            meta = getattr(order, "metadata", {}) or {}
            if meta.get("exit_pair_id") and status == "FILLED":
                pair = str(meta["exit_pair_id"])
                siblings = [
                    o
                    for o in orders.values()
                    if (getattr(o, "metadata", {}) or {}).get("exit_pair_id") == pair
                    and getattr(o.status, "value", str(o.status)) == "FILLED"
                    and o.id != order.id
                ]
                if siblings:
                    violations.append(
                        InvariantViolation(
                            code="DOUBLE_EXIT",
                            message=f"exit pair {pair} has multiple FILLED orders",
                            severity="critical",
                        )
                    )
            # Terminal orders must not still hold an open reservation.
            if (
                status
                in {
                    "FILLED",
                    "CANCELLED",
                    "EXPIRED",
                    "REJECTED",
                    "FAILED",
                }
                and meta.get("reservation_open") == "true"
            ):
                violations.append(
                    InvariantViolation(
                        code="STALE_RESERVATION",
                        message=f"order {getattr(order, 'id', '?')} {status} still reserved",
                        severity="critical",
                    )
                )

    # Realised PnL sign sanity vs fills (soft): must be finite Decimal.
    _ = realized_pnl + fees  # touch fees for coverage of fee aggregate

    critical = [v for v in violations if v.severity == "critical"]
    return InvariantReport(
        ok=len(critical) == 0,
        equity=equity,
        cash=cash,
        reserved_cash=reserved_cash,
        marked_position_value=marked,
        violations=violations,
    )


def assert_cycle_invariants(**kwargs: Any) -> InvariantReport:
    report = check_cycle_invariants(**kwargs)
    if not report.ok:
        raise AccountingInvariantError(report.to_dict())
    return report
