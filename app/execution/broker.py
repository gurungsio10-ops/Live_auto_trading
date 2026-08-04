"""Broker abstraction — PaperBroker only in this milestone."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from app.core.safety import SafetyGuard
from app.execution.paper.engine import PaperConfig, PaperTradingEngine
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.trading import Order, OrderRequest, Position, RiskEvaluation


class Broker(Protocol):
    async def submit_order(
        self, request: OrderRequest, risk: RiskEvaluation
    ) -> Order: ...

    async def cancel_order(self, order_id: str) -> Order | None: ...

    async def get_order(self, order_id: str) -> Order | None: ...

    async def list_orders(self) -> list[Order]: ...

    async def get_positions(self) -> list[Position]: ...

    async def get_balance(self) -> dict[str, Decimal]: ...

    async def close_position(
        self, symbol: str, *, mark_price: Decimal
    ) -> Order | None: ...


class PaperBroker:
    """Simulated broker wrapping ``PaperTradingEngine`` with safety checks."""

    def __init__(
        self,
        engine: PaperTradingEngine | None = None,
        *,
        config: PaperConfig | None = None,
        safety: SafetyGuard | None = None,
    ) -> None:
        self.engine = engine or PaperTradingEngine(config)
        self.safety = safety or SafetyGuard()

    async def submit_order(self, request: OrderRequest, risk: RiskEvaluation) -> Order:
        decision = self.safety.check_order_intent(market_type="spot", leverage=1)
        if not decision.allowed:
            return Order(
                id=uuid4().hex,
                client_order_id=request.client_order_id or f"blocked-{uuid4().hex[:8]}",
                idempotency_key=request.idempotency_key,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                status=OrderStatus.REJECTED,
                risk_decision=RiskDecision.REJECTED,
                risk_reason_code=RiskReasonCode.LIVE_TRADING_DISABLED,
                metadata={
                    "safety_code": decision.code,
                    "safety_reason": decision.reason,
                },
            )
        return await self.engine.submit(request, risk)

    async def cancel_order(self, order_id: str) -> Order | None:
        order = self.engine.state.orders.get(order_id)
        if order is None:
            return None
        if order.status in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }:
            return order
        updated = order.model_copy(update={"status": OrderStatus.CANCELLED})
        self.engine.state.orders[order_id] = updated
        return updated

    async def get_order(self, order_id: str) -> Order | None:
        return self.engine.state.orders.get(order_id)

    async def list_orders(self) -> list[Order]:
        return list(self.engine.state.orders.values())

    async def get_positions(self) -> list[Position]:
        return list(self.engine.state.positions.values())

    async def get_balance(self) -> dict[str, Decimal]:
        cash = self.engine.state.cash
        equity = cash
        for pos in self.engine.state.positions.values():
            equity += pos.quantity * pos.current_price
        return {
            "cash": cash,
            "equity": equity,
            "realized_pnl": self.engine.state.realized_pnl,
        }

    async def close_position(self, symbol: str, *, mark_price: Decimal) -> Order | None:
        pos = self.engine.state.positions.get(symbol)
        if pos is None or pos.quantity <= 0:
            return None
        self.engine.set_mark_price(symbol, mark_price)
        request = OrderRequest(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=pos.quantity,
            idempotency_key=f"close-{symbol}-{uuid4().hex}",
            client_order_id=f"close-{uuid4().hex[:12]}",
            reduce_only=True,
        )
        risk = RiskEvaluation(
            decision=RiskDecision.APPROVED,
            reason_code=RiskReasonCode.OK,
            approved_quantity=pos.quantity,
            message="paper close",
        )
        return await self.submit_order(request, risk)
