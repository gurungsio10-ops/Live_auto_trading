"""Paper trading engine — simulated fills with fees, slippage, partial fills."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Any
from uuid import uuid4

from app.core.time import utc_now
from app.models.domain.enums import OrderSide, OrderStatus, OrderType, RiskDecision
from app.models.domain.trading import Fill, Order, OrderRequest, Position, RiskEvaluation


@dataclass
class PaperConfig:
    initial_cash: Decimal = Decimal("10000")
    fee_rate: Decimal = Decimal("0.001")
    slippage_rate: Decimal = Decimal("0.0005")
    spread_rate: Decimal = Decimal("0.0002")
    partial_fill_fraction: Decimal = Decimal("1")  # 1 = always full fill
    mark_prices: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class PaperState:
    cash: Decimal
    positions: dict[str, Position] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)
    journal: list[dict[str, Any]] = field(default_factory=list)
    idempotency_index: dict[str, str] = field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0")


class PaperTradingEngine:
    """Simulated execution backend compatible with OrderGateway."""

    def __init__(self, config: PaperConfig | None = None) -> None:
        self.config = config or PaperConfig()
        self.state = PaperState(cash=self.config.initial_cash)

    def set_mark_price(self, symbol: str, price: Decimal) -> None:
        self.config.mark_prices[symbol] = price
        if symbol in self.state.positions:
            pos = self.state.positions[symbol]
            unrealized = (price - pos.entry_price) * pos.quantity
            self.state.positions[symbol] = pos.model_copy(
                update={"current_price": price, "unrealized_pnl": unrealized}
            )

    async def submit(self, request: OrderRequest, risk: RiskEvaluation) -> Order:
        # Idempotency: return existing order for same key
        if request.idempotency_key in self.state.idempotency_index:
            existing_id = self.state.idempotency_index[request.idempotency_key]
            return self.state.orders[existing_id]

        now = utc_now()
        order_id = uuid4().hex
        client_order_id = request.client_order_id or f"paper-{order_id[:12]}"
        order = Order(
            id=order_id,
            client_order_id=client_order_id,
            idempotency_key=request.idempotency_key,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            status=OrderStatus.RISK_PENDING,
            strategy_name=request.strategy_name,
            signal_id=request.signal_id,
            created_at=now,
            updated_at=now,
            metadata=dict(request.metadata),
        )
        self._journal("ORDER_CREATED", order)
        self.state.orders[order_id] = order
        self.state.idempotency_index[request.idempotency_key] = order_id

        if risk.decision in (RiskDecision.REJECTED, RiskDecision.HALTED):
            return self._update(order, status=OrderStatus.REJECTED, risk=risk)

        order = self._update(order, status=OrderStatus.APPROVED, risk=risk)
        order = self._update(order, status=OrderStatus.SUBMITTED, risk=risk)

        mark = self.config.mark_prices.get(request.symbol)
        if mark is None and request.order_type == OrderType.LIMIT and request.price is not None:
            mark = request.price
        if mark is None:
            return self._update(order, status=OrderStatus.FAILED, risk=risk, extra={"error": "no mark"})

        if request.order_type == OrderType.LIMIT and request.price is not None:
            # Fill limit only if market crosses
            if request.side == OrderSide.BUY and mark > request.price:
                return order  # rests unfilled (SUBMITTED)
            if request.side == OrderSide.SELL and mark < request.price:
                return order

        fill_price = self._fill_price(mark, request)
        fill_qty = (request.quantity * self.config.partial_fill_fraction).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        if fill_qty <= 0:
            return self._update(order, status=OrderStatus.FAILED, risk=risk)

        if fill_qty < request.quantity:
            order = self._apply_fill(order, fill_qty, fill_price, risk)
            return self._update(order, status=OrderStatus.PARTIALLY_FILLED, risk=risk)

        order = self._apply_fill(order, fill_qty, fill_price, risk)
        return self._update(order, status=OrderStatus.FILLED, risk=risk)

    def _apply_fill(
        self, order: Order, qty: Decimal, price: Decimal, risk: RiskEvaluation
    ) -> Order:
        fee = (price * qty * self.config.fee_rate).quantize(Decimal("0.00000001"))
        fill = Fill(
            id=uuid4().hex,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=qty,
            price=price,
            fee=fee,
            timestamp=utc_now(),
        )
        self.state.fills.append(fill)
        self._journal("FILL", fill)

        if order.side == OrderSide.BUY:
            cost = price * qty + fee
            if cost > self.state.cash:
                return self._update(order, status=OrderStatus.FAILED, risk=risk, extra={"error": "insufficient"})
            self.state.cash -= cost
            existing = self.state.positions.get(order.symbol)
            if existing:
                new_qty = existing.quantity + qty
                new_entry = (
                    (existing.entry_price * existing.quantity + price * qty) / new_qty
                )
                self.state.positions[order.symbol] = existing.model_copy(
                    update={
                        "quantity": new_qty,
                        "entry_price": new_entry,
                        "current_price": price,
                        "unrealized_pnl": (price - new_entry) * new_qty,
                    }
                )
            else:
                self.state.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=qty,
                    entry_price=price,
                    current_price=price,
                    unrealized_pnl=Decimal("0"),
                    opened_at=utc_now(),
                    strategy_name=order.strategy_name,
                )
        else:
            existing = self.state.positions.get(order.symbol)
            if existing is None or existing.quantity < qty:
                return self._update(order, status=OrderStatus.FAILED, risk=risk, extra={"error": "no position"})
            proceeds = price * qty - fee
            self.state.cash += proceeds
            realized = (price - existing.entry_price) * qty - fee
            self.state.realized_pnl += realized
            remaining = existing.quantity - qty
            if remaining == 0:
                del self.state.positions[order.symbol]
            else:
                self.state.positions[order.symbol] = existing.model_copy(
                    update={
                        "quantity": remaining,
                        "current_price": price,
                        "unrealized_pnl": (price - existing.entry_price) * remaining,
                        "realized_pnl": existing.realized_pnl + realized,
                    }
                )

        filled = order.filled_quantity + qty
        avg = price if order.average_fill_price is None else (
            (order.average_fill_price * order.filled_quantity + price * qty) / filled
        )
        return order.model_copy(
            update={
                "filled_quantity": filled,
                "average_fill_price": avg,
                "fees": order.fees + fee,
                "updated_at": utc_now(),
            }
        )

    def _fill_price(self, mark: Decimal, request: OrderRequest) -> Decimal:
        half_spread = mark * self.config.spread_rate / Decimal("2")
        slip = mark * self.config.slippage_rate
        if request.order_type == OrderType.LIMIT and request.price is not None:
            return request.price
        if request.side == OrderSide.BUY:
            return mark + half_spread + slip
        return mark - half_spread - slip

    def _update(
        self,
        order: Order,
        *,
        status: OrderStatus,
        risk: RiskEvaluation,
        extra: dict[str, Any] | None = None,
    ) -> Order:
        updated = order.model_copy(
            update={
                "status": status,
                "risk_decision": risk.decision,
                "risk_reason_code": risk.reason_code,
                "updated_at": utc_now(),
                "metadata": {**order.metadata, **(extra or {})},
            }
        )
        self.state.orders[updated.id] = updated
        self._journal("ORDER_STATUS", {"id": updated.id, "status": status.value})
        return updated

    def _journal(self, event: str, payload: Any) -> None:
        if hasattr(payload, "model_dump"):
            data = payload.model_dump(mode="json")
        else:
            data = payload
        self.state.journal.append(
            {"ts": utc_now().isoformat(), "event": event, "data": data}
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "cash": str(self.state.cash),
            "realized_pnl": str(self.state.realized_pnl),
            "positions": {
                k: v.model_dump(mode="json") for k, v in self.state.positions.items()
            },
            "orders": {
                k: v.model_dump(mode="json") for k, v in sorted(self.state.orders.items())
            },
            "fills": [f.model_dump(mode="json") for f in self.state.fills],
            "journal_events": [j["event"] for j in self.state.journal],
        }

    def export_journal_bytes(self) -> bytes:
        # Deterministic JSON for replay comparison (strip volatile ids/timestamps in caller if needed)
        return json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":")).encode()
