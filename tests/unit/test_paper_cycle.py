"""Paper trading cycle service tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.config import Settings
from app.services.paper_cycle import (
    OfflineCandleSource,
    ProvidedCandleSource,
    reset_cycle_state,
    run_paper_trading_cycle,
)
from app.services.sample_market import build_ema_crossover_candles
from app.services.trading_orchestrator import TradingOrchestrator
from app.strategies.ema_crossover import EMACrossoverStrategy


@pytest.fixture(autouse=True)
def _clean_cycle_state():
    reset_cycle_state()
    yield
    reset_cycle_state()


@pytest.mark.asyncio
async def test_cycle_buy_signal_and_idempotent_replay() -> None:
    settings = Settings(
        trading_mode="paper",
        kill_switch_enabled=False,
        paper_starting_balance=Decimal("10000"),
        _env_file=None,
    )
    strategy = EMACrossoverStrategy()
    orch = TradingOrchestrator(
        strategy=strategy,
        session_id="test-cycle",
        settings=settings,
        kill_switch_enabled=False,
    )
    source = OfflineCandleSource(force_buy_on_last=True)
    first = await run_paper_trading_cycle(
        symbol="BTC/USDT",
        timeframe="1m",
        correlation_id="corr-1",
        settings=settings,
        candle_source=source,
        orchestrator=orch,
    )
    assert first.accepted
    assert first.signal_direction in {"buy", "hold"}  # buy expected when cross works
    # Force known candles through ProvidedCandleSource for stricter assert
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    reset_cycle_state()
    orch2 = TradingOrchestrator(
        strategy=strategy,
        session_id="test-cycle-2",
        settings=settings,
        kill_switch_enabled=False,
    )
    result = await run_paper_trading_cycle(
        symbol="BTC/USDT",
        timeframe="1m",
        correlation_id="corr-2",
        settings=settings,
        candle_source=ProvidedCandleSource(candles),
        orchestrator=orch2,
    )
    assert result.signal_direction == "buy"
    assert result.order_id is not None
    assert result.order_status in {
        "FILLED",
        "PARTIALLY_FILLED",
        "APPROVED",
        "SUBMITTED",
    }

    replay = await run_paper_trading_cycle(
        symbol="BTC/USDT",
        timeframe="1m",
        correlation_id="corr-3",
        settings=settings,
        candle_source=ProvidedCandleSource(candles),
        orchestrator=orch2,
    )
    assert replay.idempotent_replay is True
    assert orch2.stats.paper_orders == 1


@pytest.mark.asyncio
async def test_cycle_hold_with_kill_switch() -> None:
    settings = Settings(
        trading_mode="paper",
        kill_switch_enabled=True,
        _env_file=None,
    )
    strategy = EMACrossoverStrategy()
    orch = TradingOrchestrator(
        strategy=strategy,
        session_id="ks",
        settings=settings,
        kill_switch_enabled=True,
    )
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    result = await run_paper_trading_cycle(
        symbol="BTC/USDT",
        timeframe="1m",
        settings=settings,
        candle_source=ProvidedCandleSource(candles),
        orchestrator=orch,
    )
    assert result.signal_direction == "buy"
    assert (
        result.risk_decision in {"HALTED", "REJECTED", None}
        or result.order_status == "REJECTED"
    )
    # When kill switch active, order should not fill
    if result.order_id:
        assert result.order_status == "REJECTED"
        assert result.risk_reason_code == "KILL_SWITCH_ACTIVE"
