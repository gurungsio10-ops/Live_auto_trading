"""EMA+RSI strategy paths — buy, sell, hold, RSI gate."""

from __future__ import annotations

from decimal import Decimal

from app.core.time import utc_now
from app.models.domain.enums import SignalDirection
from app.models.domain.trading import PortfolioState, Position
from app.services.sample_market import (
    build_ema_crossover_candles,
    build_ema_crossover_sell_candles,
)
from app.strategies.base import StrategyContext
from app.strategies.ema_rsi import EMARSIStrategy
from app.strategies.registry import get_strategy, list_strategies


def _portfolio() -> PortfolioState:
    return PortfolioState(
        cash_balance=Decimal("10000"),
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
    )


def _ctx(candles, position=None, **param_overrides):
    strategy = EMARSIStrategy()
    cfg = strategy.default_config()
    if param_overrides:
        cfg = cfg.model_copy(update={"params": {**cfg.params, **param_overrides}})
    return StrategyContext(
        candles=candles,
        portfolio=_portfolio(),
        position=position,
        config=cfg,
    )


def test_registry_includes_ema_rsi() -> None:
    ids = {s.strategy_id for s in list_strategies()}
    assert "ema_rsi" in ids
    assert get_strategy("ema_rsi").strategy_id == "ema_rsi"


def test_buy_on_ema_cross_with_rsi_confirm() -> None:
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    signal = EMARSIStrategy().evaluate(_ctx(candles))
    assert signal.direction == SignalDirection.BUY
    assert signal.suggested_stop is not None
    assert signal.suggested_target is not None
    assert "RSI" in signal.entry_rationale


def test_hold_when_rsi_gate_blocks_cross() -> None:
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    signal = EMARSIStrategy().evaluate(_ctx(candles, rsi_buy_min="101"))
    assert signal.direction == SignalDirection.HOLD
    assert "RSI" in signal.entry_rationale


def test_hold_when_already_long_on_buy_cross() -> None:
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    pos = Position(
        symbol="BTC/USDT",
        quantity=Decimal("0.1"),
        entry_price=Decimal("65000"),
        current_price=Decimal("65000"),
        unrealized_pnl=Decimal("0"),
        opened_at=utc_now(),
    )
    signal = EMARSIStrategy().evaluate(_ctx(candles, position=pos))
    assert signal.direction == SignalDirection.HOLD
    assert "already long" in signal.entry_rationale


def test_sell_on_bearish_cross_while_long() -> None:
    candles = build_ema_crossover_sell_candles()
    pos = Position(
        symbol="BTC/USDT",
        quantity=Decimal("0.1"),
        entry_price=Decimal("65000"),
        current_price=candles[-1].close,
        unrealized_pnl=Decimal("0"),
        opened_at=utc_now(),
    )
    signal = EMARSIStrategy().evaluate(_ctx(candles, position=pos))
    assert signal.direction == SignalDirection.SELL


def test_hold_insufficient_history() -> None:
    candles = build_ema_crossover_candles(force_buy_on_last=False)[:10]
    signal = EMARSIStrategy().evaluate(_ctx(candles))
    assert signal.direction == SignalDirection.HOLD
    assert "insufficient" in signal.entry_rationale.lower()
