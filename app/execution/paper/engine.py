"""Paper trading engine — simulated fills with fees, slippage, partial fills."""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from typing import Any
from uuid import uuid4

from app.core.time import utc_now
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.trading import (
    Fill,
    Order,
    OrderRequest,
    Position,
    RiskEvaluation,
)


@dataclass
class PaperConfig:
    initial_cash: Decimal = Decimal("10000")
    fee_rate: Decimal = Decimal("0.001")
    """Legacy single fee rate (used when maker/taker not set)."""
    maker_fee_rate: Decimal | None = None
    taker_fee_rate: Decimal | None = None
    slippage_rate: Decimal = Decimal("0.0005")
    spread_rate: Decimal = Decimal("0.0002")
    partial_fill_fraction: Decimal = Decimal("1")  # 1 = always full fill
    latency_ms: int = 0
    """Simulated submit latency; 0 keeps tests deterministic and fast."""
    reject_probability: Decimal = Decimal("0")
    """Optional liquidity-reject probability (0 = never; tests keep 0)."""
    seed: int | None = None
    """Deterministic RNG seed for rejection / partial-fill jitter."""
    mark_prices: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class PaperState:
    """Paper ledger.

    ``cash`` is *available* (unreserved) buying power.
    ``reserved_cash`` is capital locked for open BUY orders.
    Equity identity: ``cash + reserved_cash + marked_positions``.
    """

    cash: Decimal
    reserved_cash: Decimal = Decimal("0")
    positions: dict[str, Position] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)
    journal: list[dict[str, Any]] = field(default_factory=list)
    idempotency_index: dict[str, str] = field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0")

    @property
    def total_cash(self) -> Decimal:
        return self.cash + self.reserved_cash


class PaperTradingEngine:
    """Simulated execution backend compatible with OrderGateway."""

    def __init__(self, config: PaperConfig | None = None) -> None:
        self.config = config or PaperConfig()
        self.state = PaperState(
            cash=self.config.initial_cash, reserved_cash=Decimal("0")
        )
        self._rng = random.Random(self.config.seed)

    def set_mark_price(self, symbol: str, price: Decimal) -> None:
        self.config.mark_prices[symbol] = price
        if symbol in self.state.positions:
            pos = self.state.positions[symbol]
            unrealized = (price - pos.entry_price) * pos.quantity
            self.state.positions[symbol] = pos.model_copy(
                update={"current_price": price, "unrealized_pnl": unrealized}
            )
        # Attempt resting stop / take-profit / limit triggers on mark updates.
        self._try_trigger_resting(symbol, price)

    def _fee_rate(self, *, is_maker: bool) -> Decimal:
        if is_maker and self.config.maker_fee_rate is not None:
            return self.config.maker_fee_rate
        if not is_maker and self.config.taker_fee_rate is not None:
            return self.config.taker_fee_rate
        return self.config.fee_rate

    def _reserve_price(
        self, request: OrderRequest, mark: Decimal | None
    ) -> Decimal | None:
        """Reference price used to lock BUY notional (limit/trigger/mark)."""
        if request.order_type == OrderType.LIMIT and request.price is not None:
            return request.price
        if request.order_type in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT):
            return request.price or request.stop_loss or request.take_profit or mark
        return mark

    def _reserve_buy(
        self,
        order: Order,
        qty: Decimal,
        price: Decimal,
        risk: RiskEvaluation,
    ) -> tuple[Order, bool]:
        """Move ``qty * price`` from available cash into reserved_cash once."""
        meta = dict(order.metadata or {})
        if meta.get("reservation_open") == "true":
            return order, True
        amount = (qty * price).quantize(Decimal("0.00000001"))
        if amount <= 0:
            return order, True
        if self.state.cash < amount:
            failed = self._update(
                order,
                status=OrderStatus.FAILED,
                risk=risk,
                extra={"error": "insufficient_for_reserve"},
            )
            return failed, False
        self.state.cash -= amount
        self.state.reserved_cash += amount
        meta["reserved_notional"] = str(amount)
        meta["reserved_remaining"] = str(amount)
        meta["reservation_open"] = "true"
        self._journal(
            "RESERVE",
            {"id": order.id, "amount": str(amount), "symbol": order.symbol},
        )
        updated = order.model_copy(update={"metadata": meta, "updated_at": utc_now()})
        self.state.orders[updated.id] = updated
        return updated, True

    def _release_buy_reservation(
        self, order: Order, amount: Decimal | None = None
    ) -> Order:
        """Return reserved capital to available cash exactly once per unit.

        ``amount=None`` releases all remaining reservation (cancel/expire/reject/
        terminal fill dust). Partial fills pass a proportional ``amount``.
        Duplicate calls are no-ops when reservation is already closed.
        """
        meta = dict(order.metadata or {})
        if meta.get("reservation_open") != "true":
            return order
        remaining = Decimal(
            str(meta.get("reserved_remaining", meta.get("reserved_notional", "0")))
        )
        if remaining <= 0:
            meta["reservation_open"] = "false"
            meta["reserved_remaining"] = "0"
            updated = order.model_copy(
                update={"metadata": meta, "updated_at": utc_now()}
            )
            self.state.orders[updated.id] = updated
            return updated
        release = remaining if amount is None else min(amount, remaining)
        if release > self.state.reserved_cash:
            release = self.state.reserved_cash
        self.state.reserved_cash -= release
        self.state.cash += release
        new_remaining = remaining - release
        meta["reserved_remaining"] = str(new_remaining)
        if new_remaining <= 0:
            meta["reservation_open"] = "false"
            meta["reserved_remaining"] = "0"
        self._journal(
            "RESERVE_RELEASE",
            {
                "id": order.id,
                "amount": str(release),
                "remaining": meta["reserved_remaining"],
            },
        )
        updated = order.model_copy(update={"metadata": meta, "updated_at": utc_now()})
        self.state.orders[updated.id] = updated
        return updated

    async def submit(self, request: OrderRequest, risk: RiskEvaluation) -> Order:
        # Idempotency: return existing order for same key
        if request.idempotency_key in self.state.idempotency_index:
            existing_id = self.state.idempotency_index[request.idempotency_key]
            return self.state.orders[existing_id]

        if self.config.latency_ms > 0:
            await asyncio.sleep(self.config.latency_ms / 1000.0)

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

        # Optional insufficient-liquidity simulation (default off).
        if self.config.reject_probability > 0:
            if Decimal(str(self._rng.random())) < self.config.reject_probability:
                return self._update(
                    order,
                    status=OrderStatus.REJECTED,
                    risk=risk,
                    extra={"error": "insufficient_liquidity"},
                )

        mark = self.config.mark_prices.get(request.symbol)
        if (
            mark is None
            and request.order_type == OrderType.LIMIT
            and request.price is not None
        ):
            mark = request.price
        if mark is None and request.order_type in (
            OrderType.STOP_LOSS,
            OrderType.TAKE_PROFIT,
        ):
            # Rest until mark is known — still reserve BUY buying power.
            if request.side == OrderSide.BUY:
                reserve_px = self._reserve_price(request, mark)
                if reserve_px is not None:
                    order, ok = self._reserve_buy(
                        order,
                        risk.approved_quantity or request.quantity,
                        reserve_px,
                        risk,
                    )
                    if not ok:
                        return order
            return order
        if mark is None:
            return self._update(
                order, status=OrderStatus.FAILED, risk=risk, extra={"error": "no mark"}
            )

        # Lock BUY notional before resting or filling so concurrent buys
        # cannot double-spend available cash.
        if request.side == OrderSide.BUY:
            reserve_px = self._reserve_price(request, mark)
            if reserve_px is not None:
                order, ok = self._reserve_buy(
                    order,
                    risk.approved_quantity or request.quantity,
                    reserve_px,
                    risk,
                )
                if not ok:
                    return order

        if request.order_type == OrderType.LIMIT and request.price is not None:
            # Fill limit only if market crosses
            if request.side == OrderSide.BUY and mark > request.price:
                return order  # rests unfilled (SUBMITTED)
            if request.side == OrderSide.SELL and mark < request.price:
                return order

        if request.order_type == OrderType.STOP_LOSS:
            trigger = request.price or request.stop_loss
            if trigger is None:
                order = self._release_buy_reservation(order)
                return self._update(
                    order,
                    status=OrderStatus.REJECTED,
                    risk=risk,
                    extra={"error": "no_stop_trigger"},
                )
            # Sell stop triggers when mark <= trigger; buy stop when mark >= trigger.
            if request.side == OrderSide.SELL and mark > trigger:
                return order
            if request.side == OrderSide.BUY and mark < trigger:
                return order

        if request.order_type == OrderType.TAKE_PROFIT:
            trigger = request.price or request.take_profit
            if trigger is None:
                order = self._release_buy_reservation(order)
                return self._update(
                    order,
                    status=OrderStatus.REJECTED,
                    risk=risk,
                    extra={"error": "no_tp_trigger"},
                )
            if request.side == OrderSide.SELL and mark < trigger:
                return order
            if request.side == OrderSide.BUY and mark > trigger:
                return order

        return self._execute_fill(order, request, risk, mark)

    def _try_trigger_resting(self, symbol: str, mark: Decimal) -> None:
        """Fill resting limit/stop/tp orders when mark crosses (sync path)."""
        for order in list(self.state.orders.values()):
            if order.symbol != symbol:
                continue
            if order.status not in (
                OrderStatus.SUBMITTED,
                OrderStatus.PARTIALLY_FILLED,
            ):
                continue
            remaining = order.quantity - order.filled_quantity
            if remaining <= 0:
                continue
            price = order.price
            if order.order_type == OrderType.LIMIT and price is not None:
                if order.side == OrderSide.BUY and mark > price:
                    continue
                if order.side == OrderSide.SELL and mark < price:
                    continue
            elif order.order_type == OrderType.STOP_LOSS and price is not None:
                if order.side == OrderSide.SELL and mark > price:
                    continue
                if order.side == OrderSide.BUY and mark < price:
                    continue
            elif order.order_type == OrderType.TAKE_PROFIT and price is not None:
                if order.side == OrderSide.SELL and mark < price:
                    continue
                if order.side == OrderSide.BUY and mark > price:
                    continue
            else:
                continue
            # Build a synthetic request for fee/slippage path.
            risk = RiskEvaluation(
                decision=order.risk_decision or RiskDecision.APPROVED,
                reason_code=order.risk_reason_code or RiskReasonCode.OK,
                approved_quantity=remaining,
                message="resting_trigger",
            )
            request = OrderRequest(
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                quantity=remaining,
                price=order.price,
                strategy_name=order.strategy_name,
                idempotency_key=f"resting-{order.id}-{order.filled_quantity}",
            )
            # Bypass idempotency index for resting continuation.
            fill_price = self._fill_price(mark, request)
            is_maker = order.order_type == OrderType.LIMIT
            fill_qty = remaining
            if self.config.partial_fill_fraction < 1:
                fill_qty = (remaining * self.config.partial_fill_fraction).quantize(
                    Decimal("0.00000001"), rounding=ROUND_DOWN
                )
            if fill_qty <= 0:
                continue
            updated = self._apply_fill(
                order, fill_qty, fill_price, risk, is_maker=is_maker
            )
            if updated.status == OrderStatus.FAILED:
                continue
            if fill_qty < remaining:
                self._update(updated, status=OrderStatus.PARTIALLY_FILLED, risk=risk)
            else:
                updated = self._release_buy_reservation(updated)
                self._update(updated, status=OrderStatus.FILLED, risk=risk)

    def _execute_fill(
        self,
        order: Order,
        request: OrderRequest,
        risk: RiskEvaluation,
        mark: Decimal,
    ) -> Order:
        fill_price = self._fill_price(mark, request)
        fill_qty = (request.quantity * self.config.partial_fill_fraction).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        if fill_qty <= 0:
            return self._update(order, status=OrderStatus.FAILED, risk=risk)

        is_maker = request.order_type == OrderType.LIMIT
        if fill_qty < request.quantity:
            order = self._apply_fill(
                order, fill_qty, fill_price, risk, is_maker=is_maker
            )
            if order.status == OrderStatus.FAILED:
                return order
            return self._update(order, status=OrderStatus.PARTIALLY_FILLED, risk=risk)

        order = self._apply_fill(order, fill_qty, fill_price, risk, is_maker=is_maker)
        if order.status == OrderStatus.FAILED:
            return order
        order = self._release_buy_reservation(order)  # rounding dust
        return self._update(order, status=OrderStatus.FILLED, risk=risk)

    def _apply_fill(
        self,
        order: Order,
        qty: Decimal,
        price: Decimal,
        risk: RiskEvaluation,
        *,
        is_maker: bool = False,
    ) -> Order:
        fee_rate = self._fee_rate(is_maker=is_maker)
        fee = (price * qty * fee_rate).quantize(Decimal("0.00000001"))
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
            # Release proportional reservation back to available cash, then debit
            # actual fill cost (existing accounting path). Idempotent release.
            total_reserved = Decimal(
                str((order.metadata or {}).get("reserved_notional", "0"))
            )
            if (
                total_reserved > 0
                and (order.metadata or {}).get("reservation_open") == "true"
                and order.quantity > 0
            ):
                consume = (total_reserved * qty / order.quantity).quantize(
                    Decimal("0.00000001")
                )
                order = self._release_buy_reservation(order, consume)
            cost = price * qty + fee
            if cost > self.state.cash:
                order = self._release_buy_reservation(order)
                return self._update(
                    order,
                    status=OrderStatus.FAILED,
                    risk=risk,
                    extra={"error": "insufficient"},
                )
            self.state.cash -= cost
            existing = self.state.positions.get(order.symbol)
            if existing:
                new_qty = existing.quantity + qty
                new_entry = (
                    existing.entry_price * existing.quantity + price * qty
                ) / new_qty
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
                return self._update(
                    order,
                    status=OrderStatus.FAILED,
                    risk=risk,
                    extra={"error": "no position"},
                )
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
        avg = (
            price
            if order.average_fill_price is None
            else (
                (order.average_fill_price * order.filled_quantity + price * qty)
                / filled
            )
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

    async def cancel(self, order_id: str) -> Order:
        """Cancel an open order before fill when still technically open."""
        order = self.state.orders.get(order_id)
        if order is None:
            raise KeyError(f"unknown order {order_id}")
        cancellable = {
            OrderStatus.CREATED,
            OrderStatus.RISK_PENDING,
            OrderStatus.APPROVED,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
        }
        if order.status not in cancellable:
            return order
        # Partial fills keep filled qty; remaining is cancelled.
        order = self._release_buy_reservation(order)
        updated = order.model_copy(
            update={"status": OrderStatus.CANCELLED, "updated_at": utc_now()}
        )
        self.state.orders[order_id] = updated
        self._journal("ORDER_CANCELLED", {"id": order_id})
        return updated

    async def expire(self, order_id: str) -> Order:
        """Expire a resting order (paper exchange day/session end simulation)."""
        order = self.state.orders.get(order_id)
        if order is None:
            raise KeyError(f"unknown order {order_id}")
        if order.status not in {
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.APPROVED,
        }:
            return order
        order = self._release_buy_reservation(order)
        updated = order.model_copy(
            update={"status": OrderStatus.EXPIRED, "updated_at": utc_now()}
        )
        self.state.orders[order_id] = updated
        self._journal("ORDER_EXPIRED", {"id": order_id})
        return updated

    def snapshot(self) -> dict[str, Any]:
        return {
            "cash": str(self.state.cash),
            "reserved_cash": str(self.state.reserved_cash),
            "total_cash": str(self.state.total_cash),
            "realized_pnl": str(self.state.realized_pnl),
            "positions": {
                k: v.model_dump(mode="json") for k, v in self.state.positions.items()
            },
            "orders": {
                k: v.model_dump(mode="json")
                for k, v in sorted(self.state.orders.items())
            },
            "fills": [f.model_dump(mode="json") for f in self.state.fills],
            "journal_events": [j["event"] for j in self.state.journal],
        }

    def export_journal_bytes(self) -> bytes:
        # Deterministic JSON for replay comparison (strip volatile ids/timestamps in caller if needed)
        return json.dumps(
            self.snapshot(), sort_keys=True, separators=(",", ":")
        ).encode()
