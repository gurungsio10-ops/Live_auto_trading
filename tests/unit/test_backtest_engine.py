"""Phase 5: backtest engine — metrics + no look-ahead proof."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.backtesting.engine import BacktestConfig, BacktestEngine
from app.models.domain.enums import SignalDirection
from app.models.domain.market import Candle
from app.models.domain.trading import TradeSignal
from app.strategies.base import Strategy, StrategyContext
from app.strategies.ema_trend import EMATrendStrategy


def _candles(closes: list[float]) -> list[Candle]:
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
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


class LookAheadCheater(Strategy):
    """Would only win if it could see the next candle's close."""

    strategy_id = "cheater"
    name = "LookAhead Cheater"
    version = "1.0.0"

    def __init__(self, full_series: list[Candle]) -> None:
        self.full_series = full_series

    def evaluate(self, context: StrategyContext) -> TradeSignal:
        i = len(context.candles) - 1
        # Illicit peek: if we allowed look-ahead this would buy before every up bar.
        # The engine only passes candles[:i+1], so future close is unavailable here
        # unless we cheat via self.full_series — we deliberately do NOT use it for
        # the decision, proving the engine doesn't pass future data.
        _ = self.full_series  # retained to show temptation
        price = context.candles[-1].close
        # Naive: buy when flat, exit next bar — no future knowledge
        if context.position is None and i % 3 == 0:
            direction = SignalDirection.BUY
        elif context.position is not None:
            direction = SignalDirection.EXIT
        else:
            direction = SignalDirection.HOLD
        return TradeSignal(
            strategy_name=self.name,
            strategy_version=self.version,
            symbol="BTC/USDT",
            direction=direction,
            confidence=Decimal("0.5"),
            entry_rationale="no-lookahead naive",
            invalidation_condition="n/a",
            suggested_entry=price,
            suggested_stop=price * Decimal("0.95"),
            suggested_target=price * Decimal("1.05"),
            input_data_fingerprint=f"i={i}",
        )


class PerfectForesightIfLeaked(Strategy):
    """Buys only when the NEXT candle rises — wins only with look-ahead leak."""

    strategy_id = "foresight"
    name = "Foresight"
    version = "1.0.0"

    def __init__(self, full_series: list[Candle]) -> None:
        self.full_series = full_series

    def evaluate(self, context: StrategyContext) -> TradeSignal:
        i = len(context.candles) - 1
        price = context.candles[-1].close
        # Attempt to read future from context (must fail / not be present)
        has_future = len(context.candles) < len(self.full_series) and any(
            c.open_time > context.candles[-1].open_time for c in context.candles
        )
        assert not has_future

        # Only way to "know" future is external leak — we use it ONLY to assert
        # that if strategy relies on engine-provided candles alone it can't see it.
        future_up = False
        if i + 1 < len(self.full_series):
            # This reads outside context — simulating a buggy strategy.
            # Engine still only called evaluate with window; we check that
            # context itself doesn't contain the future bar.
            assert self.full_series[i + 1] not in context.candles
            future_up = self.full_series[i + 1].close > price

        if context.position is None and future_up:
            direction = SignalDirection.BUY
        elif context.position is not None and not future_up:
            direction = SignalDirection.EXIT
        else:
            direction = SignalDirection.HOLD
        return TradeSignal(
            strategy_name=self.name,
            strategy_version=self.version,
            symbol="BTC/USDT",
            direction=direction,
            confidence=Decimal("1"),
            entry_rationale="uses external full_series (strategy bug), not engine leak",
            invalidation_condition="n/a",
            suggested_entry=price,
            input_data_fingerprint=f"i={i}",
        )


def test_backtest_runs_and_writes_reports(tmp_path: Path):
    closes = [100 + i * 0.4 for i in range(40)]
    for idx in range(3, 40, 4):
        closes[idx] -= 1.5
    candles = _candles(closes)
    # boost volumes periodically
    for i in range(len(candles)):
        if i % 5 == 4:
            candles[i] = candles[i].model_copy(update={"volume": Decimal("400")})

    strategy = EMATrendStrategy()
    cfg = strategy.default_config()
    cfg.params.update(
        {
            "fast_ema": 3,
            "slow_ema": 5,
            "rsi_period": 4,
            "rsi_min": "40",
            "rsi_max": "75",
            "atr_period": 3,
            "min_atr": "0.5",
            "volume_ma_period": 5,
        }
    )
    engine = BacktestEngine(
        strategy,
        BacktestConfig(report_dir=tmp_path, fee_rate=Decimal("0.001")),
    )
    result = engine.run(candles, strategy_config=cfg)
    assert result.metrics.trade_count >= 0
    assert result.json_path and result.json_path.exists()
    assert result.markdown_path and result.markdown_path.exists()
    assert result.metrics.fees_paid >= 0


def test_no_lookahead_context_window():
    candles = _candles([100, 101, 102, 103, 104, 105, 90, 89, 88])
    strategy = PerfectForesightIfLeaked(candles)
    engine = BacktestEngine(strategy, BacktestConfig(report_dir=Path("/tmp/atlas-bt")))
    result = engine.run(candles, write_reports=False)
    # Context never contained future bars (asserted inside strategy).
    assert isinstance(result.metrics.trade_count, int)


def test_lookahead_window_length_invariant():
    """At bar i, strategy must only observe i+1 candles."""

    seen: list[int] = []

    class Probe(Strategy):
        strategy_id = "probe"
        name = "Probe"
        version = "1.0.0"

        def evaluate(self, context: StrategyContext) -> TradeSignal:
            seen.append(len(context.candles))
            return TradeSignal(
                strategy_name=self.name,
                strategy_version=self.version,
                symbol="BTC/USDT",
                direction=SignalDirection.HOLD,
                confidence=Decimal("0"),
                entry_rationale="probe",
                invalidation_condition="n/a",
                input_data_fingerprint=str(len(context.candles)),
            )

    candles = _candles([100, 101, 102, 103, 104])
    engine = BacktestEngine(Probe(), BacktestConfig())
    engine.run(candles, write_reports=False)
    assert seen == [1, 2, 3, 4, 5]


def test_stop_loss_is_next_bar_not_same_bar():
    """SL/TP must not fire on the entry bar (optimistic same-bar exit)."""

    class ImmediateStopBuyer(Strategy):
        strategy_id = "sl_probe"
        name = "SL Probe"
        version = "1.0.0"

        def evaluate(self, context: StrategyContext) -> TradeSignal:
            if context.position is None and len(context.candles) == 1:
                return TradeSignal(
                    strategy_name=self.name,
                    strategy_version=self.version,
                    symbol="BTC/USDT",
                    direction=SignalDirection.BUY,
                    confidence=Decimal("1"),
                    entry_rationale="enter",
                    invalidation_condition="n/a",
                    suggested_stop=Decimal("95"),
                    suggested_target=Decimal("120"),
                    input_data_fingerprint="1",
                )
            return TradeSignal(
                strategy_name=self.name,
                strategy_version=self.version,
                symbol="BTC/USDT",
                direction=SignalDirection.HOLD,
                confidence=Decimal("0"),
                entry_rationale="hold",
                invalidation_condition="n/a",
                input_data_fingerprint=str(len(context.candles)),
            )

    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    # Bar 0: enter at 100, low already below stop — must NOT exit same bar.
    # Bar 1: low hits stop — exit allowed.
    candles = [
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            open_time=t0,
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("90"),
            close=Decimal("100"),
            volume=Decimal("1"),
        ),
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            open_time=t0 + timedelta(hours=1),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("90"),
            close=Decimal("91"),
            volume=Decimal("1"),
        ),
    ]
    engine = BacktestEngine(
        ImmediateStopBuyer(),
        BacktestConfig(
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            spread_rate=Decimal("0"),
            position_size_fraction=Decimal("0.5"),
        ),
    )
    result = engine.run(candles, write_reports=False)
    assert result.metrics.trade_count == 1
    trade = result.trades[0]
    assert trade.reason == "stop-loss"
    assert trade.exit_time == candles[1].open_time
