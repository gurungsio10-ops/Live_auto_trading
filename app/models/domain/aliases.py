"""
Canonical name aliases for the paper-trading vertical-slice contract.

Atlas historically used TradeSignal / OrderRequest / PortfolioState / RiskEvaluation.
The milestone prompt names Signal / OrderIntent / PortfolioSnapshot / RiskDecision
(as a model). Prefer the historical implementations; expose aliases for clarity.
"""

from __future__ import annotations

from app.models.domain.enums import RiskDecision as RiskDecisionEnum
from app.models.domain.enums import RiskReasonCode as RiskRejectionReason
from app.models.domain.trading import (
    Balance,
    MarketSnapshot,
    OrderRequest,
    PortfolioState,
    RiskEvaluation,
    StrategyRun,
    SystemHealth,
    TradeJournalEntry,
    TradeSignal,
)

# Prompt-aligned aliases (do not duplicate validation logic).
Signal = TradeSignal
OrderIntent = OrderRequest
PortfolioSnapshot = PortfolioState
RiskDecisionModel = RiskEvaluation
RiskDecision = (
    RiskDecisionEnum  # enum; model form is RiskEvaluation / RiskDecisionModel
)

__all__ = [
    "Balance",
    "MarketSnapshot",
    "OrderIntent",
    "PortfolioSnapshot",
    "RiskDecision",
    "RiskDecisionModel",
    "RiskRejectionReason",
    "Signal",
    "StrategyRun",
    "SystemHealth",
    "TradeJournalEntry",
]
