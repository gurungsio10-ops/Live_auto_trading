"""Testnet/sandbox execution — real API surface, fake funds. Distinct from paper."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.domain.enums import OrderStatus, RiskDecision
from app.models.domain.trading import Order, OrderRequest, RiskEvaluation


@dataclass
class TestnetConfig:
    exchange_env: str = "testnet"
    rate_limit_per_minute: int = 60


@dataclass
class ExchangeTestnetClient:
    """
    Thin testnet adapter. Uses an injectable `api` client so tests never hit network.
    Requires EXCHANGE_ENV=testnet (separate from TRADING_MODE).
    """

    __test__ = False  # prevent pytest from collecting this as a test class

    api: Any
    config: TestnetConfig = field(default_factory=TestnetConfig)
    _order_times: list = field(default_factory=list)

    def __post_init__(self) -> None:
        settings = get_settings()
        if settings.exchange_env != "testnet" and self.config.exchange_env == "testnet":
            # Soft warning via attribute; live submit path will hard-fail elsewhere
            self._env_mismatch = True
        else:
            self._env_mismatch = False

    async def submit(self, request: OrderRequest, risk: RiskEvaluation) -> Order:
        if risk.decision in (RiskDecision.REJECTED, RiskDecision.HALTED):
            return Order(
                id=uuid4().hex,
                client_order_id=request.client_order_id or uuid4().hex,
                idempotency_key=request.idempotency_key,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                price=request.price,
                status=OrderStatus.REJECTED,
                risk_decision=risk.decision,
                risk_reason_code=risk.reason_code,
            )

        now = utc_now()
        self._order_times = [
            t for t in self._order_times if (now - t).total_seconds() < 60
        ]
        if len(self._order_times) >= self.config.rate_limit_per_minute:
            return Order(
                id=uuid4().hex,
                client_order_id=request.client_order_id or uuid4().hex,
                idempotency_key=request.idempotency_key,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                status=OrderStatus.FAILED,
                metadata={"error": "rate_limited"},
            )

        client_order_id = request.client_order_id or f"testnet-{uuid4().hex[:16]}"
        payload = {
            "symbol": request.symbol,
            "side": request.side.value,
            "type": request.order_type.value,
            "amount": str(request.quantity),
            "price": str(request.price) if request.price is not None else None,
            "clientOrderId": client_order_id,
        }
        raw = await self.api.create_order(payload)
        self._order_times.append(now)
        status = OrderStatus.SUBMITTED
        filled = Decimal(str(raw.get("filled") or "0"))
        if filled >= request.quantity:
            status = OrderStatus.FILLED
        elif filled > 0:
            status = OrderStatus.PARTIALLY_FILLED
        return Order(
            id=str(raw.get("id") or uuid4().hex),
            client_order_id=client_order_id,
            idempotency_key=request.idempotency_key,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            filled_quantity=filled,
            price=request.price,
            average_fill_price=(
                Decimal(str(raw["average"])) if raw.get("average") else None
            ),
            status=status,
            risk_decision=risk.decision,
            risk_reason_code=risk.reason_code,
            created_at=now,
            updated_at=now,
        )
