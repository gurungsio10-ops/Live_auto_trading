"""Tests for the live paper-trading session behind the dashboard endpoints."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.models.domain.enums import OrderStatus, RiskDecision, RiskReasonCode
from app.services import paper_cycle
from app.services.paper_session import reset_paper_session
from app.services.reconciliation import clear_reconciliation_halt


@pytest.fixture(autouse=True)
def _isolated_session(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("ENABLE_RECONCILIATION", "false")
    get_settings.cache_clear()
    paper_cycle.reset_cycle_state()
    clear_reconciliation_halt()
    yield
    paper_cycle.reset_cycle_state()
    clear_reconciliation_halt()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_start_strategy_opens_risk_checked_position():
    session = reset_paper_session()
    assert session.portfolio_summary()["open_position_count"] == 0

    await session.start_strategy("ema_trend")

    # A BUY signal was generated and turned into a filled paper order.
    signals = session.signals()
    assert signals and signals[0]["direction"] == "buy"

    orders = session.orders()
    assert orders, "expected at least one order"
    buy = orders[0]
    assert buy["side"] == "buy"
    assert buy["status"] == OrderStatus.FILLED.value
    assert buy["risk_decision"] in (
        RiskDecision.APPROVED.value,
        RiskDecision.REDUCED.value,
    )

    positions = session.positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTC/USDT"

    # Every processed order is mirrored as a risk event.
    assert session.risk_events(), "expected a risk event to be logged"


@pytest.mark.asyncio
async def test_kill_switch_halts_new_orders():
    session = reset_paper_session()
    session.set_kill_switch(True)

    order = await session.place_order(
        {
            "symbol": "BTC/USDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
        }
    )
    assert order["status"] == OrderStatus.REJECTED.value
    assert order["risk_decision"] == RiskDecision.HALTED.value
    assert order["risk_reason_code"] == RiskReasonCode.KILL_SWITCH_ACTIVE.value
    assert session.portfolio_summary()["open_position_count"] == 0


@pytest.mark.asyncio
async def test_close_position_realizes_pnl_and_clears():
    session = reset_paper_session()
    await session.start_strategy("ema_trend")
    assert session.positions()

    # Advance the market so the exit realizes a gain, then close.
    await session.run_strategy_tick("ema_trend")
    remaining = await session.close_position("BTC/USDT")
    assert remaining == []
    assert session.portfolio_summary()["open_position_count"] == 0


@pytest.mark.asyncio
async def test_pause_blocks_strategy_orders_but_keeps_signal():
    session = reset_paper_session()
    session.set_paused(True)
    await session.start_strategy("ema_trend")
    # Signal is still emitted, but no order is placed while paused.
    assert session.signals()
    assert session.orders() == []
    assert session.portfolio_summary()["trading_paused"] is True


def test_run_backtest_uses_real_engine():
    session = reset_paper_session()
    report = session.run_backtest(
        {
            "strategy_id": "ema_trend",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start": "2024-01-01",
            "end": "2024-06-01",
            "initial_cash": "10000",
        }
    )
    assert report["status"] == "completed"
    assert report["metrics"]["trade_count"] >= 1
    assert report["markdown_report"].startswith("# Backtest Report")
    assert session.backtests()


def test_settings_view_shape():
    session = reset_paper_session()
    view = session.settings_view()
    assert view["trading_mode"] == "paper"
    assert view["live_trading_enabled"] is False
    assert "max_open_positions" in view["risk_limits"]
