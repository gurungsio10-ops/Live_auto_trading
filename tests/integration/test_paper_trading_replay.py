"""
Stage 8 — deterministic offline end-to-end paper-trading replay.

No network. Feeds an embedded candle fixture through the full pipeline:
normalizer-shaped candles -> indicators/strategy -> risk engine -> paper
execution -> portfolio -> journal (DB) -> metrics, and asserts the Phase-16
acceptance invariants.
"""

from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.time import utc_now
from app.journal.store import FillORM, OrderORM, RiskDecisionORM, SignalORM
from app.models.domain.market import Candle
from app.services.trading_orchestrator import TradingOrchestrator
from app.strategies.ema_trend import EMATrendStrategy


def _series_to_candles(symbol, start, closes, *, spike_from, spike_to):
    candles = []
    prev = closes[0]
    for i, raw in enumerate(closes):
        close = raw.quantize(Decimal("0.01"))
        open_ = prev if i > 0 else (close * Decimal("0.999")).quantize(Decimal("0.01"))
        high = (max(open_, close) * Decimal("1.0015")).quantize(Decimal("0.01"))
        low = (min(open_, close) * Decimal("0.9985")).quantize(Decimal("0.01"))
        volume = Decimal(1000) + Decimal(300) * Decimal(str(abs(math.sin(i / 3.0))))
        if spike_from <= i <= spike_to:
            volume = Decimal(4500)
        candles.append(
            Candle(
                symbol=symbol,
                timeframe="1m",
                open_time=start + timedelta(minutes=i),
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                is_closed=True,
            )
        )
        prev = close
    return candles


def _entry_closes(base):
    """Uptrend + zig-zag tail that lands RSI mid-band -> a genuine BUY."""
    n = 60
    closes = [base * (Decimal(1) + Decimal("0.0015") * Decimal(i)) for i in range(n)]
    tail = [
        "0.004",
        "-0.006",
        "0.003",
        "-0.007",
        "0.004",
        "-0.006",
        "0.005",
        "-0.007",
        "0.004",
        "-0.006",
        "0.005",
        "-0.007",
        "0.004",
        "0.006",
    ]
    k0 = n - len(tail)
    c = closes[k0 - 1]
    for k, r in enumerate(tail):
        c = c * (Decimal(1) + Decimal(r))
        closes[k0 + k] = c
    return closes


def build_replay_candles(symbol="BTC/USDT", start=None):
    """Warm-up (HOLD) -> BUY -> hold -> downtrend EMA cross-under (EXIT)."""
    start = start or (utc_now() - timedelta(minutes=200))
    closes = _entry_closes(Decimal(30000))
    last = closes[-1]
    for j in range(1, 26):  # ramp down to force cross-under -> EXIT
        closes.append(last * (Decimal(1) - Decimal("0.004") * Decimal(j)))
    return _series_to_candles(symbol, start, closes, spike_from=46, spike_to=59)


def build_entry_candles(symbol="BTC/USDT", start=None):
    start = start or utc_now()
    return _series_to_candles(
        symbol, start, _entry_closes(Decimal(30000)), spike_from=46, spike_to=59
    )


@pytest.mark.asyncio
async def test_offline_replay_full_lifecycle(db_session):
    from app.journal.store import JournalStore

    journal = JournalStore(db_session)
    orch = TradingOrchestrator(
        strategy=EMATrendStrategy(),
        session_id="replay-session-01",
        journal=journal,
    )

    outcomes = []
    for candle in build_replay_candles():
        outcomes.append(await orch.process_candle(candle))

    directions = [o.signal_direction for o in outcomes if o.accepted]
    fills = [o for o in outcomes if o.order_status == "FILLED"]
    buy_fills = [o for o in fills if o.signal_direction == "buy"]
    exit_fills = [o for o in fills if o.signal_direction == "exit"]

    # Stage 8 fixture must trigger BUY, HOLD, EXIT, and a completed trade.
    assert "hold" in directions
    assert len(buy_fills) >= 1, "expected at least one BUY fill"
    assert len(exit_fills) >= 1, "expected at least one EXIT fill (completed trade)"

    snap = orch.snapshot()
    assert snap["paper_orders"] == 2
    assert snap["fills"] == 2
    assert Decimal(snap["fees"]) > 0  # fees are included
    assert snap["open_positions"] == 0  # trade completed / flat
    assert snap["risk_approvals"] == 2

    # --- persistence assertions (journal DB) ---
    order_count = (
        await db_session.execute(select(func.count()).select_from(OrderORM))
    ).scalar_one()
    risk_count = (
        await db_session.execute(select(func.count()).select_from(RiskDecisionORM))
    ).scalar_one()
    fill_count = (
        await db_session.execute(select(func.count()).select_from(FillORM))
    ).scalar_one()
    signal_count = (
        await db_session.execute(select(func.count()).select_from(SignalORM))
    ).scalar_one()

    assert order_count == 2
    assert fill_count == 2
    # Every actionable order has a persisted risk decision.
    assert risk_count == order_count
    # Every strategy decision (incl. HOLD) is journalled.
    assert signal_count == snap["signals_generated"]

    # Every persisted order carries a risk decision + reason.
    orders = (await db_session.execute(select(OrderORM))).scalars().all()
    coids = [o.client_order_id for o in orders]
    assert len(coids) == len(set(coids)), "no duplicate client order ids"
    for o in orders:
        assert o.risk_decision is not None
        assert o.risk_reason_code is not None

    risk_rows = (await db_session.execute(select(RiskDecisionORM))).scalars().all()
    for r in risk_rows:
        assert r.reason_code  # decision reasons recorded
        assert r.message is not None

    # Money is persisted as Decimal (Numeric column round-trips to Decimal).
    for o in orders:
        assert isinstance(o.quantity, Decimal)
        assert isinstance(o.fees, Decimal)

    # Domain objects use tz-aware UTC timestamps (SQLite storage strips tz on
    # read-back, so assert on the in-memory domain orders, not the ORM rows).
    domain_orders = list(orch.paper.state.orders.values())
    assert domain_orders
    for o in domain_orders:
        assert o.created_at.tzinfo is not None
        assert o.created_at.utcoffset() == timedelta(0)
        assert isinstance(o.quantity, Decimal)

    # Balance accounting reconciles exactly from the fills (fees included),
    # independent of the realized-P&L model.
    from app.models.domain.enums import OrderSide

    cash = Decimal(10000)
    for fill in orch.paper.state.fills:
        if fill.side == OrderSide.BUY:
            cash -= fill.price * fill.quantity + fill.fee
        else:
            cash += fill.price * fill.quantity - fill.fee
    assert cash == orch.paper.state.cash
    # Flat position => equity equals cash balance.
    assert Decimal(snap["equity"]) == Decimal(snap["current_balance"])
    assert Decimal(snap["realized_pnl"]) != 0  # a real trade settled


@pytest.mark.asyncio
async def test_replaying_same_candle_does_not_duplicate_trade(db_session):
    from app.journal.store import JournalStore

    orch = TradingOrchestrator(
        strategy=EMATrendStrategy(),
        session_id="replay-session-02",
        journal=JournalStore(db_session),
    )
    candles = build_replay_candles()
    for candle in candles:
        await orch.process_candle(candle)

    orders_before = orch.stats.paper_orders
    order_rows_before = (
        await db_session.execute(select(func.count()).select_from(OrderORM))
    ).scalar_one()

    # Re-feed every candle again — all are duplicates/out-of-order.
    for candle in candles:
        out = await orch.process_candle(candle)
        assert not out.accepted  # rejected as duplicate/out-of-order

    assert orch.stats.paper_orders == orders_before  # no new orders
    order_rows_after = (
        await db_session.execute(select(func.count()).select_from(OrderORM))
    ).scalar_one()
    assert order_rows_after == order_rows_before  # no duplicate trades persisted


@pytest.mark.asyncio
async def test_kill_switch_blocks_order_creation_in_pipeline(db_session):
    from app.journal.store import JournalStore

    orch = TradingOrchestrator(
        strategy=EMATrendStrategy(),
        session_id="replay-session-03",
        journal=JournalStore(db_session),
        kill_switch_enabled=True,  # phase-16 safety posture
    )
    for candle in build_entry_candles():
        await orch.process_candle(candle)

    # A BUY was generated but every order was HALTED — no fills, no position.
    assert orch.stats.risk_rejections >= 1
    assert orch.stats.paper_orders == 0
    assert orch.snapshot()["open_positions"] == 0

    risk_rows = (await db_session.execute(select(RiskDecisionORM))).scalars().all()
    assert any(r.reason_code == "KILL_SWITCH_ACTIVE" for r in risk_rows)


def test_orchestrator_has_no_execution_or_advisory_bypass():
    """AI/news never authorize execution; no live exchange import in the loop."""
    source = Path("app/services/trading_orchestrator.py").read_text()
    assert "app.ai" not in source
    assert "app.news" not in source
    assert "ExchangeTestnetClient" not in source
    assert "app.execution.exchange" not in source
    # The only execution backend is the paper engine, reached via the gateway.
    assert "OrderGateway" in source
    assert "PaperTradingEngine" in source
