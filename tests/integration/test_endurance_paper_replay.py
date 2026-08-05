"""
Endurance-style paper replay (deterministic, offline).

Replays many candles, restarts session mid-run, duplicates cycles,
and verifies accounting invariants + zero duplicate fills.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time import utc_now
from app.db.base import Base, create_engine
from app.models.domain.market import Candle
from app.services import paper_cycle
from app.services.paper_session import (
    get_paper_session,
    hydrate_paper_session_from_db,
    persist_paper_session,
    reset_paper_session,
)
from app.services.reconciliation import (
    clear_reconciliation_halt,
    run_paper_reconciliation,
)
from app.services.sample_market import build_ema_crossover_candles


def _extend_candles(symbol: str, timeframe: str, days: int = 30) -> list[Candle]:
    """Build a long deterministic series (~days of 1h bars)."""
    bars = max(days * 24, 120)
    base = build_ema_crossover_candles(
        symbol=symbol,
        interval=timeframe,
        base_price=Decimal("65000"),
        force_buy_on_last=True,
    )
    # Repeat/shift the fixture series to reach endurance length.
    out: list[Candle] = []
    start = utc_now() - timedelta(hours=bars)
    seed = [c for c in base if c.is_closed]
    for i in range(bars):
        src = seed[i % len(seed)]
        # Mild deterministic drift so prices stay valid.
        factor = Decimal("1") + (Decimal(i % 17) - Decimal("8")) * Decimal("0.0005")
        close = (src.close * factor).quantize(Decimal("0.01"))
        open_ = (src.open * factor).quantize(Decimal("0.01"))
        high = max(open_, close) * Decimal("1.001")
        low = min(open_, close) * Decimal("0.999")
        out.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time=start + timedelta(hours=i),
                open=open_,
                high=high.quantize(Decimal("0.01")),
                low=low.quantize(Decimal("0.01")),
                close=close,
                volume=src.volume,
                is_closed=True,
            )
        )
    return out


@pytest.mark.asyncio
async def test_endurance_replay_with_restart_and_duplicates(tmp_path):
    clear_reconciliation_halt()
    paper_cycle.reset_cycle_state()
    reset_paper_session()

    db_path = tmp_path / "endurance.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    symbol = "BTC/USDT"
    timeframe = "1h"
    candles = _extend_candles(symbol, timeframe, days=30)
    assert len(candles) >= 720

    # Process in windows of 80 bars, advancing tip each time.
    fill_ids: set[str] = set()
    order_ids: set[str] = set()
    mid = len(candles) // 2

    for tip in range(60, mid, 15):
        window = candles[: tip + 1]
        source = paper_cycle.ProvidedCandleSource(candles=window)
        await paper_cycle.run_paper_trading_cycle(
            symbol=symbol,
            timeframe=timeframe,
            strategy_id="ema_crossover",
            candle_source=source,
            candle_limit=120,
        )
        # Duplicate request for same tip
        dup = await paper_cycle.run_paper_trading_cycle(
            symbol=symbol,
            timeframe=timeframe,
            strategy_id="ema_crossover",
            candle_source=source,
            candle_limit=120,
        )
        assert dup.idempotent_replay is True or dup.reject_reason in {
            "RECONCILIATION_HALT",
            "CYCLE_LOCK_HELD",
        }, (dup.idempotent_replay, dup.reject_reason, dup.message)
        session = get_paper_session()
        for f in session.paper.state.fills:
            fill_ids.add(f.id)
        for o in session.paper.state.orders:
            order_ids.add(o)

    # Persist + simulate restart mid-run
    async with factory() as db:
        await persist_paper_session(db, correlation_id="endurance-mid")
        await paper_cycle.persist_cycle_keys(db)
        keys = await paper_cycle.load_persisted_cycle_keys(db)

    paper_cycle.reset_cycle_state()
    reset_paper_session()
    paper_cycle.set_processed_cycle_keys(keys)
    async with factory() as db:
        await hydrate_paper_session_from_db(db)

    cash_after_restart = get_paper_session().paper.state.cash
    assert cash_after_restart >= Decimal("0")

    for tip in range(mid, len(candles), 20):
        window = candles[: tip + 1]
        source = paper_cycle.ProvidedCandleSource(candles=window)
        await paper_cycle.run_paper_trading_cycle(
            symbol=symbol,
            timeframe=timeframe,
            strategy_id="ema_crossover",
            candle_source=source,
            candle_limit=120,
        )
        # intentional duplicate
        await paper_cycle.run_paper_trading_cycle(
            symbol=symbol,
            timeframe=timeframe,
            strategy_id="ema_crossover",
            candle_source=source,
            candle_limit=120,
        )

    session = get_paper_session()
    paper = session.paper
    final_fill_ids = {f.id for f in paper.state.fills}
    # No duplicate fill identities beyond what ledger already holds uniquely.
    assert len(final_fill_ids) == len(paper.state.fills)

    # Accounting invariant
    marked = sum(
        (p.quantity * p.current_price for p in paper.state.positions.values()),
        Decimal("0"),
    )
    equity = paper.state.cash + marked
    assert paper.state.cash >= Decimal("0")
    for pos in paper.state.positions.values():
        assert pos.quantity >= Decimal("0")

    # Filled qty never exceeds order qty
    for order in paper.state.orders.values():
        filled_qty = sum(
            (f.quantity for f in paper.state.fills if f.order_id == order.id),
            Decimal("0"),
        )
        assert filled_qty <= order.quantity

    recon = await run_paper_reconciliation(persist=False)
    assert recon.healthy is True, recon.detail
    assert abs(Decimal(recon.equity) - equity) <= Decimal("0.05")

    await engine.dispose()
