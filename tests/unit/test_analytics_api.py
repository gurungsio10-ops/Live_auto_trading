"""HTTP coverage for performance analytics endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.analytics.models
from app.analytics.trade_journal import ClosedTrade, TradeJournalService
from app.core.config import get_settings
from app.db.base import Base
from app.main import app
from app.services.paper_session import reset_paper_session


@pytest.fixture
async def analytics_client(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "analytics-api.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENABLE_TRADING_SCHEDULER", "false")
    monkeypatch.setenv("ENABLE_OPS_SSE", "false")
    monkeypatch.setenv("ENABLE_RECONCILIATION", "false")
    get_settings.cache_clear()
    reset_paper_session()

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        await TradeJournalService(db).record(
            ClosedTrade(
                id="ct-api-1",
                strategy_name="ema_crossover",
                symbol="BTC/USDT",
                side="sell",
                entry_time=datetime(2026, 8, 5, 10, tzinfo=UTC),
                exit_time=datetime(2026, 8, 5, 12, tzinfo=UTC),
                entry_price=Decimal("50000"),
                exit_price=Decimal("51000"),
                quantity=Decimal("0.01"),
                fees=Decimal("1"),
                slippage=Decimal("0.25"),
                gross_pnl=Decimal("10"),
                net_pnl=Decimal("9"),
                roi_pct=Decimal("1.8"),
                duration_seconds=7200,
                exit_reason="signal_exit",
                risk_score=Decimal("15"),
                market_regime="ranging",
                paper_session_id="sess-api",
            )
        )
    await engine.dispose()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    reset_paper_session()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_analytics_overview_and_performance(analytics_client: AsyncClient):
    ov = await analytics_client.get("/analytics/overview")
    assert ov.status_code == 200
    body = ov.json()
    assert body["trade_count"] >= 1
    assert "win_rate" in body
    assert "equity_curve" in body
    assert body["banner"].startswith("PAPER")

    perf = await analytics_client.get("/api/analytics/performance")
    assert perf.status_code == 200
    pdata = perf.json()
    assert "metrics" in pdata
    assert "monthly_performance" in pdata
    assert "strategies" in pdata


@pytest.mark.asyncio
async def test_analytics_trades_detail_risk_reports_export(
    analytics_client: AsyncClient,
):
    trades = await analytics_client.get("/analytics/trades")
    assert trades.status_code == 200
    assert trades.json()["count"] >= 1

    detail = await analytics_client.get("/analytics/trades/ct-api-1")
    assert detail.status_code == 200
    assert detail.json()["id"] == "ct-api-1"

    missing = await analytics_client.get("/analytics/trades/does-not-exist")
    assert missing.status_code == 404

    risk = await analytics_client.get("/analytics/risk")
    assert risk.status_code == 200
    assert "kill_switch_enabled" in risk.json()

    strat = await analytics_client.get("/analytics/strategies")
    assert strat.status_code == 200
    assert isinstance(strat.json()["strategies"], list)

    curve = await analytics_client.get("/analytics/equity-curve")
    assert curve.status_code == 200
    assert "balance_history" in curve.json()

    report = await analytics_client.get("/analytics/reports/daily")
    assert report.status_code == 200
    assert report.json()["period"] == "daily"

    csv_exp = await analytics_client.get("/analytics/export/trades?format=csv")
    assert csv_exp.status_code == 200
    assert "trade_id" in csv_exp.text

    json_exp = await analytics_client.get("/analytics/export/trades?format=json")
    assert json_exp.status_code == 200

    rep_csv = await analytics_client.get("/analytics/export/report/weekly?format=csv")
    assert rep_csv.status_code == 200
