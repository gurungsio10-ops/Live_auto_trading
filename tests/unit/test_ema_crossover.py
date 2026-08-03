"""Deterministic EMA crossover strategy tests."""

from __future__ import annotations

from decimal import Decimal

from app.core.time import utc_now
from app.models.domain.enums import SignalDirection
from app.models.domain.market import Candle
from app.models.domain.trading import PortfolioState, Position
from app.services.sample_market import build_ema_crossover_candles
from app.strategies.base import StrategyConfig, StrategyContext
from app.strategies.ema_crossover import EMACrossoverStrategy


def _portfolio() -> PortfolioState:
    return PortfolioState(
        cash_balance=Decimal("10000"),
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
    )


def _ctx(candles: list[Candle], position: Position | None = None) -> StrategyContext:
    strategy = EMACrossoverStrategy()
    return StrategyContext(
        candles=candles,
        portfolio=_portfolio(),
        position=position,
        indicators={},
        config=strategy.default_config(),
    )


def test_buy_on_bullish_crossover() -> None:
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    signal = EMACrossoverStrategy().evaluate(_ctx(candles))
    assert signal.direction == SignalDirection.BUY
    assert signal.metadata["confidence_kind"] == "rule_derived_not_predictive"
    assert "fast_ema" in signal.metadata["indicators"]


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
    signal = EMACrossoverStrategy().evaluate(_ctx(candles, position=pos))
    assert signal.direction == SignalDirection.HOLD


def test_sell_on_bearish_crossover_with_position() -> None:
    from app.services.sample_market import build_ema_crossover_sell_candles

    candles = build_ema_crossover_sell_candles()
    pos = Position(
        symbol="BTC/USDT",
        quantity=Decimal("0.1"),
        entry_price=Decimal("65000"),
        current_price=candles[-1].close,
        unrealized_pnl=Decimal("0"),
        opened_at=utc_now(),
    )
    signal = EMACrossoverStrategy().evaluate(_ctx(candles, position=pos))
    assert signal.direction == SignalDirection.SELL


def test_hold_insufficient_history() -> None:
    candles = build_ema_crossover_candles(force_buy_on_last=False)[:10]
    signal = EMACrossoverStrategy().evaluate(_ctx(candles))
    assert signal.direction == SignalDirection.HOLD
    assert "insufficient history" in signal.entry_rationale


def test_hold_on_duplicate_candle() -> None:
    candles = build_ema_crossover_candles(force_buy_on_last=False)
    bad = list(candles)
    bad.append(candles[-1])  # duplicate open_time
    signal = EMACrossoverStrategy().evaluate(_ctx(bad))
    assert signal.direction == SignalDirection.HOLD
    assert "duplicate" in signal.entry_rationale.lower()


def test_hold_on_invalid_ordering() -> None:
    candles = build_ema_crossover_candles(force_buy_on_last=False)
    bad = list(candles)
    # Swap last two timestamps to break ordering while keeping unique times
    a, b = bad[-2], bad[-1]
    bad[-2] = b.model_copy(update={"open_time": a.open_time})
    bad[-1] = a.model_copy(update={"open_time": b.open_time})
    # Now sequence is not sorted by open_time
    signal = EMACrossoverStrategy().evaluate(_ctx(bad))
    assert signal.direction == SignalDirection.HOLD


def test_determinism() -> None:
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    s = EMACrossoverStrategy()
    a = s.evaluate(_ctx(candles))
    b = s.evaluate(_ctx(candles))
    assert a.direction == b.direction
    assert a.input_data_fingerprint == b.input_data_fingerprint
    assert a.metadata["indicators"] == b.metadata["indicators"]


def test_default_params_are_9_21() -> None:
    cfg: StrategyConfig = EMACrossoverStrategy().default_config()
    assert cfg.params["fast_ema"] == 9
    assert cfg.params["slow_ema"] == 21
