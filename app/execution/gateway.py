"""
Order submission gateway.

Strategies and API must call this — never the paper/exchange engines directly.
Every order is evaluated by the risk engine first.
"""

from __future__ import annotations

from typing import Protocol

from app.models.domain.enums import OrderStatus, RiskDecision
from app.models.domain.trading import Order, OrderRequest, RiskEvaluation
from app.risk.engine import RiskContext, RiskEngine, get_risk_engine


class ExecutionBackend(Protocol):
    async def submit(self, request: OrderRequest, risk: RiskEvaluation) -> Order: ...


class RiskBlockedError(PermissionError):
    def __init__(self, evaluation: RiskEvaluation) -> None:
        self.evaluation = evaluation
        super().__init__(
            f"Order blocked: {evaluation.decision} / {evaluation.reason_code}"
        )


class OrderGateway:
    """Single entrypoint for order submission."""

    def __init__(
        self,
        backend: ExecutionBackend,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        self.backend = backend
        self.risk_engine = risk_engine or get_risk_engine()

    async def submit(self, request: OrderRequest, context: RiskContext) -> Order:
        evaluation = self.risk_engine.evaluate(request, context)
        if evaluation.decision in (RiskDecision.REJECTED, RiskDecision.HALTED):
            raise RiskBlockedError(evaluation)
        if (
            evaluation.decision == RiskDecision.REDUCED
            and evaluation.approved_quantity is not None
        ):
            request = request.model_copy(
                update={"quantity": evaluation.approved_quantity}
            )
        order = await self.backend.submit(request, evaluation)
        # Tag risk outcome on the order
        return order.model_copy(
            update={
                "risk_decision": evaluation.decision,
                "risk_reason_code": evaluation.reason_code,
                "status": (
                    order.status
                    if order.status != OrderStatus.CREATED
                    else OrderStatus.APPROVED
                ),
            }
        )
