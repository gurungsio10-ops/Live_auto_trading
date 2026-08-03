"""
Stage 9 — orchestrator failure-mode and safety tests.

Covers the failure modes that live in the orchestration layer: bad-candle
rejection (incomplete/duplicate/out-of-order/stale), indicator warm-up, strategy
exceptions, insufficient balance, duplicate-order idempotency, kill-switch
halting, live-mode gating, and journal-failure resilience.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.core.time import utc_now
from app.execution.paper.engine import PaperConfig, PaperTradingEngine
from app.models.domain.market import Candle
from app.services.sample_market import build_sample_candles
from app.services.trading_orchestrator import TradingOrchestrator
from app.strategies.base import Strategy, StrategyConfig
from app.strategies.ema_trend import EMATrendStrategy


def _candle(
    symbol="BTC/USDT", *, minutes_ago=1, close="30000", is_closed=True, open_time=None
):
    ot = open_time or (utc_now() - timedelta(minutes=minutes_ago))
    c = Decimal(close)
    return Candle(
        symbol=symbol,
        timeframe="1m",
        open_time=ot,
        open=c,
        high=(c * Decimal("1.001")).quantize(Decimal("0.01")),
        low=(c * Decimal("0.999")).quantize(Decimal("0.01")),
        close=c,
        volume=Decimal(1000),
        is_closed=is_closed,
    )


def _orch(**kw):
    return TradingOrchestrator(
        strategy=EMATrendStrategy(), session_id="unit-test", **kw
    )


@pytest.mark.asyncio
async def test_incomplete_candle_rejected():
    orch = _orch()
    out = await orch.process_candle(_candle(is_closed=False))
    assert not out.accepted
    assert out.reject_reason == "INCOMPLETE_CANDLE"
    assert orch.stats.candles_rejected == 1


@pytest.mark.asyncio
async def test_duplicate_candle_rejected():
    orch = _orch()
    c = _candle()
    assert (await orch.process_candle(c)).accepted
    out = await orch.process_candle(c)
    assert not out.accepted
    assert out.reject_reason == "DUPLICATE_CANDLE"


@pytest.mark.asyncio
async def test_out_of_order_candle_rejected():
    orch = _orch()
    now = utc_now()
    await orch.process_candle(_candle(open_time=now))
    out = await orch.process_candle(_candle(open_time=now - timedelta(minutes=1)))
    assert not out.accepted
    assert out.reject_reason == "OUT_OF_ORDER_CANDLE"


@pytest.mark.asyncio
async def test_stale_candle_rejected():
    orch = _orch(max_candle_age_seconds=30)
    out = await orch.process_candle(
        _candle(open_time=utc_now() - timedelta(minutes=10))
    )
    assert not out.accepted
    assert out.reject_reason == "STALE_CANDLE"


@pytest.mark.asyncio
async def test_warmup_period_holds_without_orders():
    orch = _orch()
    # Fewer candles than the strategy needs -> HOLD, never an order.
    for i in range(10):
        out = await orch.process_candle(
            _candle(open_time=utc_now() - timedelta(minutes=20 - i))
        )
        assert out.accepted
        assert out.signal_direction == "hold"
    assert orch.stats.paper_orders == 0


class _ExplodingStrategy(Strategy):
    strategy_id = "boom"
    name = "Exploding"
    version = "1.0.0"

    def evaluate(self, context):
        raise RuntimeError("strategy bug")

    def default_config(self):
        return StrategyConfig(strategy_id=self.strategy_id, version=self.version)


@pytest.mark.asyncio
async def test_strategy_exception_is_contained():
    orch = TradingOrchestrator(strategy=_ExplodingStrategy(), session_id="unit-test")
    out = await orch.process_candle(_candle())
    # Session survives; error is counted; no order.
    assert out.accepted
    assert out.reject_reason == "STRATEGY_ERROR"
    assert orch.stats.errors == 1
    assert orch.stats.paper_orders == 0


@pytest.mark.asyncio
async def test_insufficient_balance_blocks_entry():
    # Tiny account -> a BUY's notional is below the minimum -> rejected, no position.
    orch = TradingOrchestrator(
        strategy=EMATrendStrategy(),
        session_id="unit-test",
        paper_engine=PaperTradingEngine(PaperConfig(initial_cash=Decimal(5))),
    )
    for candle in build_sample_candles():
        await orch.process_candle(candle)
    assert orch.snapshot()["open_positions"] == 0
    assert orch.stats.fills == 0
    assert orch.stats.risk_rejections >= 1


@pytest.mark.asyncio
async def test_kill_switch_halts_all_orders():
    orch = _orch(kill_switch_enabled=True)
    for candle in build_sample_candles():
        await orch.process_candle(candle)
    assert orch.stats.paper_orders == 0
    assert orch.stats.risk_rejections >= 1


@pytest.mark.asyncio
async def test_live_mode_without_gates_is_blocked():
    live_settings = Settings(trading_mode="live", live_trading_enabled=False)
    orch = TradingOrchestrator(
        strategy=EMATrendStrategy(), session_id="unit-test", settings=live_settings
    )
    for candle in build_sample_candles():
        await orch.process_candle(candle)
    # Live gating rejects every actionable order; nothing fills.
    assert orch.stats.fills == 0
    assert orch.stats.risk_rejections >= 1


class _FlakyJournal:
    """Journal double whose writes always fail (DB transaction failure)."""

    async def record_signal(self, *a, **k):
        raise RuntimeError("db down")

    async def record_risk_decision(self, *a, **k):
        raise RuntimeError("db down")

    async def record_order(self, *a, **k):
        raise RuntimeError("db down")

    async def record_fill(self, *a, **k):
        raise RuntimeError("db down")

    async def record_system_event(self, *a, **k):
        raise RuntimeError("db down")


@pytest.mark.asyncio
async def test_journal_failure_does_not_break_trading_loop():
    orch = TradingOrchestrator(
        strategy=EMATrendStrategy(),
        session_id="unit-test",
        journal=_FlakyJournal(),  # type: ignore[arg-type]
    )
    for candle in build_sample_candles():
        await orch.process_candle(candle)
    # Trade still executed in-memory; journal errors were counted, not raised.
    assert orch.stats.paper_orders == 2
    assert orch.stats.errors > 0


@pytest.mark.asyncio
async def test_idempotent_client_order_ids():
    orch = _orch()
    for candle in build_sample_candles():
        await orch.process_candle(candle)
    orders = list(orch.paper.state.orders.values())
    coids = [o.client_order_id for o in orders]
    # Deterministic + unique per (session, symbol, open_time, direction).
    assert len(coids) == len(set(coids))
    for o in orders:
        assert o.client_order_id.startswith("unit-tes-")
