"""Domain models package."""

from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
    SignalDirection,
    StrategyGovernanceStatus,
)
from app.models.domain.market import Candle, SymbolInfo
from app.models.domain.trading import (
    Balance,
    Fill,
    MarketSnapshot,
    Order,
    OrderRequest,
    PortfolioState,
    Position,
    RiskEvaluation,
    StrategyRun,
    SystemHealth,
    TradeJournalEntry,
    TradeSignal,
)

# Prompt-aligned aliases
Signal = TradeSignal
OrderIntent = OrderRequest
PortfolioSnapshot = PortfolioState
RiskRejectionReason = RiskReasonCode

__all__ = [
    "Balance",
    "Candle",
    "Fill",
    "MarketSnapshot",
    "Order",
    "OrderIntent",
    "OrderRequest",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PortfolioSnapshot",
    "PortfolioState",
    "Position",
    "RiskDecision",
    "RiskEvaluation",
    "RiskReasonCode",
    "RiskRejectionReason",
    "Signal",
    "SignalDirection",
    "StrategyGovernanceStatus",
    "StrategyRun",
    "SymbolInfo",
    "SystemHealth",
    "TradeJournalEntry",
    "TradeSignal",
]
