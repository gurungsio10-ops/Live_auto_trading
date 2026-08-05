"""Strategy registry by ID."""

from __future__ import annotations

from app.strategies.base import Strategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.ema_crossover import EMACrossoverStrategy
from app.strategies.ema_rsi import EMARSIStrategy
from app.strategies.ema_trend import EMATrendStrategy
from app.strategies.rsi_mean_reversion import RSIMeanReversionStrategy

_REGISTRY: dict[str, Strategy] = {}


def register(strategy: Strategy) -> None:
    _REGISTRY[strategy.strategy_id] = strategy


def get_strategy(strategy_id: str) -> Strategy:
    if strategy_id not in _REGISTRY:
        raise KeyError(f"Unknown strategy: {strategy_id}")
    return _REGISTRY[strategy_id]


def list_strategies() -> list[Strategy]:
    return list(_REGISTRY.values())


def bootstrap_default_strategies() -> None:
    defaults: list[Strategy] = [
        EMACrossoverStrategy(),
        EMARSIStrategy(),
        EMATrendStrategy(),
        RSIMeanReversionStrategy(),
        BreakoutStrategy(),
    ]
    for strategy in defaults:
        if strategy.strategy_id not in _REGISTRY:
            register(strategy)


bootstrap_default_strategies()
