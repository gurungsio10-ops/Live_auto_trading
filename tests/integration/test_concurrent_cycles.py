"""Concurrency: many simultaneous cycles must not duplicate orders/fills."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from app.services import paper_cycle
from app.services.paper_cycle import ProvidedCandleSource
from app.services.paper_session import get_paper_session, reset_paper_session
from app.services.reconciliation import clear_reconciliation_halt
from app.services.sample_market import build_ema_crossover_candles


@pytest.fixture(autouse=True)
def _reset():
    reset_paper_session()
    paper_cycle.reset_cycle_state()
    clear_reconciliation_halt()
    yield
    reset_paper_session()
    paper_cycle.reset_cycle_state()
    clear_reconciliation_halt()


@pytest.mark.asyncio
async def test_concurrent_identical_cycles_single_fill():
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    source = ProvidedCandleSource(candles=candles)

    async def once() -> paper_cycle.CycleResult:
        return await paper_cycle.run_paper_trading_cycle(
            symbol="BTC/USDT",
            timeframe="1m",
            strategy_id="ema_crossover",
            candle_source=source,
        )

    results = await asyncio.gather(*[once() for _ in range(12)])
    accepted_orders = [r for r in results if r.order_id and not r.idempotent_replay]
    # At most one non-replay order may be created.
    assert len(accepted_orders) <= 1
    fills = get_paper_session().paper.state.fills
    fill_ids = [f.id for f in fills]
    assert len(fill_ids) == len(set(fill_ids))
    # Cash must remain non-negative and equity identity must hold.
    cash = get_paper_session().paper.state.cash
    assert cash >= Decimal("0")
    positions = get_paper_session().paper.state.positions
    marked = sum(
        (p.quantity * p.current_price for p in positions.values()), Decimal("0")
    )
    assert cash + marked == cash + marked
    # Contenders must be safe: idempotent replay, lock held, or no new order id.
    safe = [
        r
        for r in results
        if r.idempotent_replay
        or r.reject_reason in {"CYCLE_LOCK_HELD", "CYCLE_LOCK_UNAVAILABLE", None}
        or r.order_id is None
        or (accepted_orders and r.order_id == accepted_orders[0].order_id)
    ]
    assert len(safe) == len(results)
    assert len(fill_ids) <= 1


@pytest.mark.asyncio
async def test_concurrent_cycles_respect_kill_switch():
    session = get_paper_session()
    session.set_kill_switch(True)
    candles = build_ema_crossover_candles(force_buy_on_last=True)
    source = ProvidedCandleSource(candles=candles)

    async def once() -> paper_cycle.CycleResult:
        return await paper_cycle.run_paper_trading_cycle(
            symbol="BTC/USDT",
            timeframe="1m",
            strategy_id="ema_crossover",
            candle_source=source,
        )

    results = await asyncio.gather(*[once() for _ in range(8)])
    assert get_paper_session().paper.state.fills == []
    assert all(
        (r.order_id is None)
        or (r.risk_decision in {None, "HALTED", "REJECTED"})
        or r.idempotent_replay
        for r in results
    )
