"""Phase 5: backtest engine — metrics + no look-ahead proof."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

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


def test_empty_candles_raises():
    engine = BacktestEngine(EMATrendStrategy(), BacktestConfig())
    with pytest.raises(ValueError, match="candles must not be empty"):
        engine.run([], write_reports=False)


def test_fees_and_slippage_worsen_fill():
    class AlwaysBuyThenExit(Strategy):
        strategy_id = "roundtrip"
        name = "Roundtrip"
        version = "1.0.0"

        def evaluate(self, context: StrategyContext) -> TradeSignal:
            price = context.candles[-1].close
            if context.position is None and len(context.candles) == 1:
                direction = SignalDirection.BUY
            elif context.position is not None and len(context.candles) == 2:
                direction = SignalDirection.EXIT
            else:
                direction = SignalDirection.HOLD
            return TradeSignal(
                strategy_name=self.name,
                strategy_version=self.version,
                symbol="BTC/USDT",
                direction=direction,
                confidence=Decimal("1"),
                entry_rationale="roundtrip",
                invalidation_condition="n/a",
                suggested_entry=price,
                input_data_fingerprint=str(len(context.candles)),
            )

    candles = _candles([100, 100, 100])
    engine = BacktestEngine(
        AlwaysBuyThenExit(),
        BacktestConfig(
            fee_rate=Decimal("0.01"),
            slippage_rate=Decimal("0.01"),
            spread_rate=Decimal("0.01"),
            position_size_fraction=Decimal("0.5"),
        ),
    )
    result = engine.run(candles, write_reports=False)
    assert result.metrics.trade_count == 1
    trade = result.trades[0]
    assert trade.entry_price > Decimal("100")
    assert trade.exit_price is not None and trade.exit_price < Decimal("100")
    assert trade.fees > 0
    assert trade.slippage_cost > 0
    assert trade.pnl < 0
    assert isinstance(result.metrics.total_return, Decimal)
    assert result.metrics.fees_paid > 0


def test_force_close_at_end_of_data():
    class BuyAndHold(Strategy):
        strategy_id = "hold"
        name = "BuyAndHold"
        version = "1.0.0"

        def evaluate(self, context: StrategyContext) -> TradeSignal:
            price = context.candles[-1].close
            direction = (
                SignalDirection.BUY
                if context.position is None and len(context.candles) == 1
                else SignalDirection.HOLD
            )
            return TradeSignal(
                strategy_name=self.name,
                strategy_version=self.version,
                symbol="BTC/USDT",
                direction=direction,
                confidence=Decimal("1"),
                entry_rationale="hold",
                invalidation_condition="n/a",
                suggested_entry=price,
                input_data_fingerprint=str(len(context.candles)),
            )

    candles = _candles([100, 110, 120])
    result = BacktestEngine(
        BuyAndHold(),
        BacktestConfig(position_size_fraction=Decimal("0.5"), fee_rate=Decimal("0")),
    ).run(candles, write_reports=False)
    assert result.metrics.trade_count == 1
    assert result.trades[0].reason == "end-of-data"
    assert result.trades[0].exit_price is not None
    assert result.trades[0].pnl > 0


def test_backtest_replay_is_deterministic(tmp_path: Path):
    closes = [100 + (i % 5) - 1 for i in range(30)]
    candles = _candles(closes)
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
    engine = BacktestEngine(strategy, BacktestConfig(report_dir=tmp_path))
    a = engine.run(candles, strategy_config=cfg, write_reports=False)
    b = engine.run(candles, strategy_config=cfg, write_reports=False)
    assert a.metrics.trade_count == b.metrics.trade_count
    assert a.metrics.total_return == b.metrics.total_return
    assert a.metrics.max_drawdown == b.metrics.max_drawdown
    assert [(t, str(eq)) for t, eq in a.equity_curve] == [
        (t, str(eq)) for t, eq in b.equity_curve
    ]


@pytest.mark.asyncio
async def test_backtest_on_postgres_candles(tmp_path: Path):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from app.models.database.market import CandleORM

    engine_db = create_async_engine(
        "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas"
    )
    Session = async_sessionmaker(engine_db, expire_on_commit=False, class_=AsyncSession)
    try:
        async with Session() as session:
            rows = (
                await session.scalars(
                    select(CandleORM)
                    .where(
                        CandleORM.symbol == "BTC/USDT",
                        CandleORM.timeframe == "1h",
                    )
                    .order_by(CandleORM.open_time.asc())
                )
            ).all()
            candles = [
                Candle(
                    symbol=r.symbol,
                    timeframe=r.timeframe,
                    open_time=r.open_time,
                    close_time=r.close_time,
                    open=r.open,
                    high=r.high,
                    low=r.low,
                    close=r.close,
                    volume=r.volume,
                    is_closed=r.is_closed,
                )
                for r in rows
            ]
    finally:
        await engine_db.dispose()

    if len(candles) < 8:
        return

    strategy = EMATrendStrategy()
    cfg = strategy.default_config()
    cfg.params.update(
        {
            "fast_ema": 3,
            "slow_ema": 5,
            "rsi_period": 3,
            "rsi_min": "0",
            "rsi_max": "100",
            "atr_period": 3,
            "min_atr": "0",
            "volume_ma_period": 3,
        }
    )
    result = BacktestEngine(strategy, BacktestConfig(report_dir=tmp_path)).run(
        candles, strategy_config=cfg, write_reports=True
    )
    assert result.metrics.trade_count >= 0
    assert isinstance(result.metrics.net_return, Decimal)
    assert result.json_path and result.json_path.exists()
    assert len(result.equity_curve) == len(candles)
