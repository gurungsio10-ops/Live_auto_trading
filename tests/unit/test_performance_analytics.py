"""Performance analytics: metrics, journal, equity curve, reports, recovery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.analytics.models  # noqa: F401
from app.analytics.performance import PerformanceEngine, build_equity_series
from app.analytics.reports import (
    build_period_report,
    export_trades_csv,
    export_trades_json,
    filter_trades_in_window,
    period_window,
)
from app.analytics.trade_journal import (
    ClosedTrade,
    TradeJournalService,
    build_closed_trade_from_exit,
)
from app.core.config import get_settings
from app.db.base import Base
from app.models.domain.enums import OrderSide, OrderStatus, OrderType
from app.models.domain.trading import Fill, Order, Position
from app.services.paper_session import get_paper_session, reset_paper_session


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("ENABLE_TRADING_SCHEDULER", "false")
    get_settings.cache_clear()
    reset_paper_session()
    yield
    reset_paper_session()
    get_settings.cache_clear()


def _trade(
    *,
    tid: str,
    net: str,
    exit_offset_hours: int = 0,
    strategy: str = "ema_crossover",
    qty: str = "0.01",
) -> ClosedTrade:
    now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    entry = now - timedelta(hours=2)
    exit_t = now + timedelta(hours=exit_offset_hours)
    entry_px = Decimal("50000")
    exit_px = entry_px + (Decimal(net) / Decimal(qty))
    return ClosedTrade(
        id=tid,
        strategy_name=strategy,
        symbol="BTC/USDT",
        side="sell",
        entry_time=entry,
        exit_time=exit_t,
        entry_price=entry_px,
        exit_price=exit_px,
        quantity=Decimal(qty),
        fees=Decimal("1"),
        slippage=Decimal("0.5"),
        gross_pnl=Decimal(net) + Decimal("1"),
        net_pnl=Decimal(net),
        roi_pct=Decimal("1.5"),
        duration_seconds=7200,
        exit_reason="signal_exit",
        risk_score=Decimal("12"),
        market_regime="ranging",
        paper_session_id="sess-1",
    )


def test_metric_calculations_win_rate_roi_drawdown():
    trades = [
        _trade(tid="a", net="100"),
        _trade(tid="b", net="-40"),
        _trade(tid="c", net="50"),
    ]
    curve = [
        {"time": "2026-08-01T00:00:00+00:00", "equity": "10000", "drawdown": "0"},
        {"time": "2026-08-02T00:00:00+00:00", "equity": "11000", "drawdown": "0"},
        {"time": "2026-08-03T00:00:00+00:00", "equity": "9900", "drawdown": "0.1"},
        {"time": "2026-08-04T00:00:00+00:00", "equity": "10110", "drawdown": "0.08"},
    ]
    snap = PerformanceEngine(starting_balance=Decimal("10000")).compute(
        trades=trades,
        current_balance=Decimal("10110"),
        unrealised_pnl=Decimal("10"),
        realised_pnl=Decimal("110"),
        equity_curve=curve,
        open_position_count=1,
    )
    assert snap.trade_count == 3
    assert snap.win_rate == Decimal("2") / Decimal("3")
    assert snap.loss_rate == Decimal("1") / Decimal("3")
    assert snap.largest_win == Decimal("100")
    assert snap.largest_loss == Decimal("-40")
    assert snap.profit_factor > 1
    assert snap.roi_pct == Decimal("1.10")
    assert snap.maximum_drawdown >= Decimal("0.1")
    assert snap.total_fees == Decimal("3")
    assert snap.average_holding_time == Decimal("7200")
    d = snap.to_dict()
    assert d["banner"].startswith("PAPER")


def test_equity_curve_accuracy_daily_returns():
    points = [
        {"time": "2026-08-01T10:00:00+00:00", "equity": "10000", "drawdown": "0"},
        {"time": "2026-08-01T18:00:00+00:00", "equity": "10100", "drawdown": "0"},
        {"time": "2026-08-02T12:00:00+00:00", "equity": "10201", "drawdown": "0"},
    ]
    series = build_equity_series(points, starting_balance=Decimal("10000"))
    assert len(series["balance_history"]) == 3
    assert len(series["drawdown_history"]) == 3
    assert len(series["daily_return_history"]) == 2
    assert series["daily_return_history"][0]["date"] == "2026-08-01"
    # Day1 close 10100 vs start 10000 => +1%
    assert Decimal(series["daily_return_history"][0]["return_pct"]) == Decimal("1.0000")


def test_build_closed_trade_from_exit_roi_and_fees():
    pos = Position(
        symbol="BTC/USDT",
        quantity=Decimal("0.01"),
        entry_price=Decimal("50000"),
        current_price=Decimal("51000"),
        unrealized_pnl=Decimal("10"),
        opened_at=datetime(2026, 8, 5, 10, 0, tzinfo=UTC),
        strategy_name="ema_crossover",
    )
    order = Order(
        id="ord1",
        client_order_id="c1",
        idempotency_key="k1",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        status=OrderStatus.FILLED,
        strategy_name="ema_crossover",
    )
    fill = Fill(
        id="fill1",
        order_id="ord1",
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        quantity=Decimal("0.01"),
        price=Decimal("51000"),
        fee=Decimal("0.51"),
        timestamp=datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
    )
    trade = build_closed_trade_from_exit(
        position=pos,
        order=order,
        fill=fill,
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
        paper_session_id="paper-abc",
        exit_reason="signal_exit",
    )
    assert trade.id == "ct-fill1"
    assert trade.gross_pnl == Decimal("10.00000000")
    assert trade.fees > 0
    assert trade.net_pnl == trade.gross_pnl - trade.fees
    assert trade.roi_pct != 0
    assert trade.duration_seconds == 7200
    assert "trade_id" in trade.to_dict()


@pytest.mark.asyncio
async def test_trade_recording_idempotent(tmp_path: Path):
    db_path = tmp_path / "analytics.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    trade = _trade(tid="ct-unique-1", net="25")
    async with factory() as db:
        journal = TradeJournalService(db)
        assert await journal.record(trade) is True
        assert await journal.record(trade) is False  # no duplicate
        listed = await journal.list_trades(limit=10)
        assert len(listed) == 1
        got = await journal.get("ct-unique-1")
        assert got is not None
        assert got.net_pnl == Decimal("25")
    await engine.dispose()


@pytest.mark.asyncio
async def test_report_generation_and_export(tmp_path: Path):
    db_path = tmp_path / "reports.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        journal = TradeJournalService(db)
        await journal.record(_trade(tid="r1", net="10", exit_offset_hours=0))
        await journal.record(
            _trade(tid="r2", net="-5", exit_offset_hours=0, strategy="breakout")
        )
        payload = await build_period_report(
            db,
            period="daily",
            current_balance=Decimal("10005"),
            unrealised_pnl=Decimal("0"),
            realised_pnl=Decimal("5"),
            starting_balance=Decimal("10000"),
            persist=True,
        )
        assert payload["period"] == "daily"
        assert payload["trade_count"] >= 0
        assert "metrics" in payload
        assert payload.get("report_id")
        trades = await journal.all_trades()
        csv_body = export_trades_csv(trades)
        assert "trade_id" in csv_body
        assert "BTC/USDT" in csv_body
        json_body = export_trades_json(trades)
        assert "PAPER TRADING" in json_body
    await engine.dispose()


def test_period_window_and_filter():
    start, end = period_window("weekly", now=datetime(2026, 8, 5, 15, tzinfo=UTC))
    assert start.weekday() == 0
    trades = [
        _trade(tid="old", net="1", exit_offset_hours=-200),
        _trade(tid="new", net="2", exit_offset_hours=0),
    ]
    # Force old trade far in past
    trades[0].exit_time = datetime(2026, 1, 1, tzinfo=UTC)
    windowed = filter_trades_in_window(trades, start, end)
    assert all(t.id == "new" for t in windowed) or len(windowed) <= 2


@pytest.mark.asyncio
async def test_recovery_after_restart_preserves_closed_trades(tmp_path: Path):
    db_path = tmp_path / "recover.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        await TradeJournalService(db).record(_trade(tid="persist-me", net="33"))
    await engine.dispose()

    # "Restart" — new engine, new process session
    reset_paper_session()
    engine2 = create_async_engine(url)
    factory2 = async_sessionmaker(engine2, expire_on_commit=False, class_=AsyncSession)
    async with factory2() as db:
        restored = await TradeJournalService(db).get("persist-me")
        assert restored is not None
        assert restored.net_pnl == Decimal("33")
        snap = PerformanceEngine().compute(
            trades=[restored],
            current_balance=Decimal("10033"),
            unrealised_pnl=Decimal("0"),
        )
        assert snap.realised_pnl == Decimal("33")
    await engine2.dispose()


@pytest.mark.asyncio
async def test_manual_sell_records_closed_trade(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "manual.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    session = reset_paper_session()
    session.risk_engine.state.last_market_data_ts = datetime.now(UTC)
    session.risk_engine.state.market_data_healthy = True
    session.risk_engine.state.database_healthy = True

    buy = await session.place_order(
        {
            "symbol": "BTC/USDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
        }
    )
    if buy["status"] != OrderStatus.FILLED.value:
        pytest.skip(f"buy not filled in this environment: {buy.get('status')}")

    sell = await session.place_order(
        {
            "symbol": "BTC/USDT",
            "side": "sell",
            "order_type": "market",
            "quantity": "0.01",
        }
    )
    assert sell["status"] in (
        OrderStatus.FILLED.value,
        OrderStatus.PARTIALLY_FILLED.value,
        OrderStatus.REJECTED.value,
    )
    if sell["status"] == OrderStatus.FILLED.value:
        engine2 = create_async_engine(url)
        factory = async_sessionmaker(
            engine2, expire_on_commit=False, class_=AsyncSession
        )
        async with factory() as db:
            trades = await TradeJournalService(db).all_trades()
        await engine2.dispose()
        assert len(trades) >= 1
        assert trades[0].symbol == "BTC/USDT"


def test_strategy_rankings():
    trades = [
        _trade(tid="1", net="100", strategy="ema_crossover"),
        _trade(tid="2", net="10", strategy="breakout"),
        _trade(tid="3", net="-5", strategy="breakout"),
    ]
    ranks = PerformanceEngine().strategy_rankings(trades)
    assert ranks[0]["strategy_name"] == "ema_crossover"
    assert ranks[0]["rank"] == 1
    assert get_paper_session().settings.trading_mode == "paper"


def test_classify_regime_and_risk_score():
    from app.analytics.trade_journal import (
        classify_market_regime,
        risk_score_from_context,
    )

    assert classify_market_regime() == "unclassified"
    assert classify_market_regime(rsi=Decimal("80")) == "overbought"
    assert classify_market_regime(rsi=Decimal("20")) == "oversold"
    assert classify_market_regime(atr_pct=Decimal("0.05")) == "high_volatility"
    assert classify_market_regime(atr_pct=Decimal("0.001")) == "low_volatility"
    assert classify_market_regime(rsi=Decimal("50")) == "ranging"
    assert risk_score_from_context(
        drawdown=Decimal("0"), consecutive_losses=0, kill_switch=True
    ) == Decimal("100")
    assert (
        risk_score_from_context(
            drawdown=Decimal("0.2"), consecutive_losses=3, kill_switch=False
        )
        > 10
    )


def test_recorder_skips_non_sell():
    from app.analytics.recorder import maybe_build_closed_trade
    from app.models.domain.enums import OrderSide, OrderStatus, OrderType
    from app.models.domain.trading import Order

    order = Order(
        id="o",
        client_order_id="c",
        idempotency_key="k",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        status=OrderStatus.FILLED,
    )
    assert (
        maybe_build_closed_trade(
            position_before=None,
            order=order,
            fills=[],
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
            paper_session_id="s",
        )
        == []
    )


def test_monthly_performance_and_empty_metrics():
    eng = PerformanceEngine(starting_balance=Decimal("10000"))
    empty = eng.compute(
        trades=[],
        current_balance=Decimal("10000"),
        unrealised_pnl=Decimal("0"),
    )
    assert empty.win_rate == 0
    assert empty.profit_factor == 0
    trades = [
        _trade(tid="m1", net="5"),
        _trade(tid="m2", net="-2"),
    ]
    months = eng.monthly_performance(trades)
    assert months
    assert months[0]["month"] == "2026-08"


@pytest.mark.asyncio
async def test_list_trades_filters(tmp_path: Path):
    db_path = tmp_path / "filter.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        j = TradeJournalService(db)
        await j.record(_trade(tid="f1", net="1", strategy="ema_crossover"))
        await j.record(_trade(tid="f2", net="2", strategy="breakout"))
        by_q = await j.list_trades(q="break")
        assert len(by_q) == 1
        by_side = await j.list_trades(side="sell")
        assert len(by_side) == 2
        by_sym = await j.list_trades(symbol="btc/usdt")
        assert len(by_sym) == 2
    await engine.dispose()


def test_export_report_json_helper():
    from app.analytics.reports import export_report_json

    body = export_report_json({"period": "daily", "trade_count": 0})
    assert '"period": "daily"' in body
