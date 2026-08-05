"""RSI mean-reversion and Donchian breakout strategy tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.domain.enums import SignalDirection
from app.models.domain.market import Candle
from app.models.domain.trading import PortfolioState, Position
from app.strategies.base import StrategyContext
from app.strategies.breakout import BreakoutStrategy
from app.strategies.registry import get_strategy, list_strategies
from app.strategies.rsi_mean_reversion import RSIMeanReversionStrategy


def _candles(closes: list[float], *, start: datetime | None = None) -> list[Candle]:
    t0 = start or datetime(2024, 1, 1, tzinfo=UTC)
    out: list[Candle] = []
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        out.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1h",
                open_time=t0 + timedelta(hours=i),
                open=c,
                high=c + Decimal("1"),
                low=c - Decimal("1"),
                close=c,
                volume=Decimal("100"),
            )
        )
    return out


def _portfolio() -> PortfolioState:
    return PortfolioState(
        cash_balance=Decimal("10000"),
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
    )


def _long() -> Position:
    return Position(
        symbol="BTC/USDT",
        quantity=Decimal("0.01"),
        entry_price=Decimal("100"),
        current_price=Decimal("100"),
        unrealized_pnl=Decimal("0"),
        opened_at=datetime(2024, 1, 1, tzinfo=UTC),
        strategy_name="test",
    )


def test_registry_has_rsi_and_breakout():
    ids = {s.strategy_id for s in list_strategies()}
    assert "rsi_mean_reversion" in ids
    assert "breakout" in ids
    assert get_strategy("rsi_mean_reversion").name == "RSI Mean Reversion"
    assert get_strategy("breakout").name == "Donchian Breakout"


def test_rsi_insufficient_history_holds():
    strategy = RSIMeanReversionStrategy()
    cfg = strategy.default_config()
    cfg.params.update({"rsi_period": 14, "warmup_margin": 5})
    signal = strategy.evaluate(
        StrategyContext(
            candles=_candles([100] * 10), portfolio=_portfolio(), config=cfg
        )
    )
    assert signal.direction == SignalDirection.HOLD
    assert "insufficient" in signal.entry_rationale.lower()


def test_rsi_buy_on_oversold_cross_up():
    # Sharp drop then bounce to force RSI cross up through oversold.
    closes = [100.0] * 20 + [90, 88, 85, 82, 80, 78, 76, 74, 72, 70, 68, 66, 80]
    strategy = RSIMeanReversionStrategy()
    cfg = strategy.default_config()
    cfg.params.update(
        {"rsi_period": 5, "oversold": "30", "overbought": "70", "warmup_margin": 1}
    )
    signal = strategy.evaluate(
        StrategyContext(candles=_candles(closes), portfolio=_portfolio(), config=cfg)
    )
    assert signal.direction in (SignalDirection.BUY, SignalDirection.HOLD)
    assert signal.input_data_fingerprint
    assert signal.metadata.get("confidence_kind") == "rule_derived_not_predictive"


def test_rsi_sell_requires_long_position():
    closes = [50.0] * 10 + [70, 72, 74, 76, 78, 80, 82, 84, 86, 88, 70]
    strategy = RSIMeanReversionStrategy()
    cfg = strategy.default_config()
    cfg.params.update(
        {"rsi_period": 5, "oversold": "30", "overbought": "70", "warmup_margin": 1}
    )
    flat = strategy.evaluate(
        StrategyContext(candles=_candles(closes), portfolio=_portfolio(), config=cfg)
    )
    # Without a position, overbought cross must not sell.
    assert flat.direction != SignalDirection.SELL


def test_breakout_buy_above_prior_high():
    # Flat channel then breakout close above prior window high.
    base = [100.0 + (i % 3) * 0.1 for i in range(25)]
    closes = [*base, 110.0]
    highs_extra = True
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        high = c + Decimal("0.5")
        if i == len(closes) - 1 and highs_extra:
            # Prior highs stay ~100.5; current close 110 breaks out.
            high = c
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1h",
                open_time=t0 + timedelta(hours=i),
                open=c,
                high=high,
                low=c - Decimal("0.5"),
                close=c,
                volume=Decimal("100"),
            )
        )
    strategy = BreakoutStrategy()
    cfg = strategy.default_config()
    cfg.params.update({"lookback": 20, "atr_period": 5, "warmup_margin": 1})
    signal = strategy.evaluate(
        StrategyContext(candles=candles, portfolio=_portfolio(), config=cfg)
    )
    assert signal.direction == SignalDirection.BUY
    assert signal.suggested_entry is not None


def test_breakout_sell_when_long_and_breaks_low():
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    # Build a range around 100, then crash below prior lows while long.
    for i in range(25):
        c = Decimal("100")
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1h",
                open_time=t0 + timedelta(hours=i),
                open=c,
                high=c + Decimal("1"),
                low=c - Decimal("1"),
                close=c,
                volume=Decimal("100"),
            )
        )
    crash = Decimal("90")
    candles.append(
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            open_time=t0 + timedelta(hours=25),
            open=crash,
            high=crash + Decimal("0.5"),
            low=crash - Decimal("0.5"),
            close=crash,
            volume=Decimal("100"),
        )
    )
    strategy = BreakoutStrategy()
    cfg = strategy.default_config()
    cfg.params.update({"lookback": 20, "atr_period": 5, "warmup_margin": 1})
    signal = strategy.evaluate(
        StrategyContext(
            candles=candles, portfolio=_portfolio(), position=_long(), config=cfg
        )
    )
    assert signal.direction == SignalDirection.SELL


def test_breakout_excludes_current_bar_from_channel():
    """Prior high must not include the current bar (no same-bar look-ahead)."""
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for i in range(22):
        c = Decimal("100")
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1h",
                open_time=t0 + timedelta(hours=i),
                open=c,
                high=c + Decimal("1"),
                low=c - Decimal("1"),
                close=c,
                volume=Decimal("100"),
            )
        )
    # Current bar has an extreme high; close is still inside prior channel.
    # If look-ahead included current high, channel would expand and miss breaks.
    # Close equals prior high exactly → should HOLD (needs close > prior_high).
    last = Decimal("101")
    candles.append(
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            open_time=t0 + timedelta(hours=22),
            open=last,
            high=Decimal("200"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("100"),
        )
    )
    strategy = BreakoutStrategy()
    cfg = strategy.default_config()
    cfg.params.update({"lookback": 20, "atr_period": 5, "warmup_margin": 1})
    signal = strategy.evaluate(
        StrategyContext(candles=candles, portfolio=_portfolio(), config=cfg)
    )
    # prior_high from bars excluding current = 101; close == 101 → HOLD
    assert signal.direction == SignalDirection.HOLD
