"""Base strategy interface. No LLM in the decision path."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.domain.market import Candle
from app.models.domain.trading import PortfolioState, Position, TradeSignal


class StrategyConfig(BaseModel):
    strategy_id: str
    version: str = "1.0.0"
    params: dict[str, Any] = Field(default_factory=dict)


class StrategyContext(BaseModel):
    candles: list[Candle]
    portfolio: PortfolioState
    position: Position | None = None
    indicators: dict[str, Any] = Field(default_factory=dict)
    config: StrategyConfig


class Strategy(ABC):
    strategy_id: str
    version: str = "1.0.0"
    name: str

    @abstractmethod
    def evaluate(self, context: StrategyContext) -> TradeSignal:
        """Return a TradeSignal. Must be deterministic — no LLM/randomness."""

    def default_config(self) -> StrategyConfig:
        return StrategyConfig(strategy_id=self.strategy_id, version=self.version)

    @staticmethod
    def fingerprint(candles: list[Candle], params: dict[str, Any]) -> str:
        if not candles:
            return "empty"
        last = candles[-1]
        return (
            f"{last.symbol}:{last.timeframe}:{last.open_time.isoformat()}:"
            f"{last.close}:{len(candles)}:{sorted(params.items())}"
        )
