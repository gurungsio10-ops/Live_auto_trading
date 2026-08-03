"""Phase 4: EMA Trend strategy deterministic signal tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.domain.enums import SignalDirection
from app.models.domain.market import Candle
from app.models.domain.trading import PortfolioState, Position
from app.strategies.base import StrategyConfig, StrategyContext
from app.strategies.ema_trend import EMATrendStrategy
from app.strategies.registry import get_strategy, list_strategies

SHORT_PARAMS = {
    "fast_ema": 3,
    "slow_ema": 5,
    "rsi_period": 4,
    "rsi_min": "40",
    "rsi_max": "75",
    "atr_period": 3,
    "min_atr": "0.5",
    "volume_ma_period": 5,
    "stop_atr_multiple": "1.5",
    "target_atr_multiple": "3.0",
    "max_holding_bars": 48,
}


def _candles(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
    start: datetime | None = None,
) -> list[Candle]:
    t0 = start or datetime(2024, 1, 1, tzinfo=UTC)
    out: list[Candle] = []
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        vol = Decimal(str(volumes[i])) if volumes else Decimal("100")
        out.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1h",
                open_time=t0 + timedelta(hours=i),
                open=c,
                high=c + Decimal("1"),
                low=c - Decimal("1"),
                close=c,
                volume=vol,
            )
        )
    return out


def _portfolio() -> PortfolioState:
    return PortfolioState(
        cash_balance=Decimal("10000"),
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
    )


def _oscillating_uptrend(n: int = 12) -> list[float]:
    closes: list[float] = []
    price = 100.0
    for i in range(n):
        price = price - 1.5 if i % 4 == 3 else price + 1.0
        closes.append(price)
    return closes


def test_registry_has_ema_trend():
    ids = {s.strategy_id for s in list_strategies()}
    assert "ema_trend" in ids
    assert get_strategy("ema_trend").name == "EMA Trend Strategy"


def test_buy_signal_on_uptrend():
    closes = _oscillating_uptrend(10)
    volumes = [100.0] * 9 + [400.0]
    candles = _candles(closes, volumes=volumes)
    strategy = EMATrendStrategy()
    cfg = strategy.default_config()
    cfg.params.update(SHORT_PARAMS)
    signal = strategy.evaluate(
        StrategyContext(candles=candles, portfolio=_portfolio(), config=cfg)
    )
    assert signal.direction == SignalDirection.BUY
    assert signal.suggested_stop is not None
    assert signal.suggested_target is not None
    assert signal.strategy_name == strategy.name
    assert signal.input_data_fingerprint


def test_hold_on_downtrend():
    closes = [120 - i * 1.5 for i in range(20)]
    candles = _candles(closes)
    strategy = EMATrendStrategy()
    cfg = strategy.default_config()
    cfg.params.update(SHORT_PARAMS)
    signal = strategy.evaluate(
        StrategyContext(candles=candles, portfolio=_portfolio(), config=cfg)
    )
    assert signal.direction == SignalDirection.HOLD


def test_exit_on_ema_cross_under():
    closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 100]
    candles = _candles(closes)
    strategy = EMATrendStrategy()
    cfg = strategy.default_config()
    cfg.params.update(SHORT_PARAMS)
    position = Position(
        symbol="BTC/USDT",
        quantity=Decimal("1"),
        entry_price=Decimal("105"),
        current_price=candles[-1].close,
        unrealized_pnl=Decimal("0"),
        opened_at=candles[0].open_time,
        stop_loss=Decimal("1"),
        take_profit=Decimal("100000"),
    )
    signal = strategy.evaluate(
        StrategyContext(
            candles=candles,
            portfolio=_portfolio(),
            position=position,
            indicators={"bars_held": 3},
            config=cfg,
        )
    )
    assert signal.direction == SignalDirection.EXIT
    assert signal.metadata.get("exit_reason") == "ema cross-under"


def test_insufficient_history_holds():
    candles = _candles([100, 101, 102])
    strategy = EMATrendStrategy()
    ctx = StrategyContext(
        candles=candles,
        portfolio=_portfolio(),
        config=StrategyConfig(strategy_id="ema_trend", params=SHORT_PARAMS),
    )
    assert strategy.evaluate(ctx).direction == SignalDirection.HOLD
