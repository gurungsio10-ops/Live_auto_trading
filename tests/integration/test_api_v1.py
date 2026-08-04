"""HTTP tests for /api/v1 paper-trading surface."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure admin token before app settings cache.
os.environ["ADMIN_API_TOKEN"] = "test-admin-token"
os.environ.setdefault("TRADING_MODE", "paper")

from app.core.config import get_settings
from app.main import app
from app.services import paper_cycle
from app.services.paper_session import reset_paper_session


@pytest.fixture(autouse=True)
def _reset_state():
    get_settings.cache_clear()
    os.environ["ADMIN_API_TOKEN"] = "test-admin-token"
    get_settings.cache_clear()
    paper_cycle.reset_cycle_state()
    reset_paper_session()
    yield
    paper_cycle.reset_cycle_state()
    reset_paper_session()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_health_ready_status() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h = await client.get("/api/v1/health")
        assert h.status_code == 200
        assert h.json()["status"] == "ok"
        r = await client.get("/api/v1/ready")
        assert r.status_code == 200
        s = await client.get("/api/v1/system/status")
        assert s.status_code == 200
        assert s.json()["trading_mode"] == "paper"


@pytest.mark.asyncio
async def test_run_paper_cycle_and_portfolio() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.post(
            "/api/v1/paper/cycle/run",
            json={"symbol": "BTC/USDT", "timeframe": "1m"},
        )
        assert denied.status_code in {401, 503}
        res = await client.post(
            "/api/v1/paper/cycle/run",
            json={"symbol": "BTC/USDT", "timeframe": "1m"},
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["simulated"] is True
        assert body["signal_direction"] in {"buy", "sell", "hold"}
        port = await client.get("/api/v1/portfolio")
        assert port.status_code == 200
        assert port.json()["simulated"] is True
        strat = await client.get("/api/v1/strategy/latest")
        assert strat.status_code == 200


@pytest.mark.asyncio
async def test_kill_switch_requires_admin_token() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.post("/api/v1/system/kill-switch/activate", json={})
        assert denied.status_code in {401, 503}
        ok = await client.post(
            "/api/v1/system/kill-switch/activate",
            json={"reason": "test"},
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert ok.status_code == 200
        assert ok.json()["kill_switch_enabled"] is True
        status = await client.get("/api/v1/system/status")
        assert status.json()["kill_switch_enabled"] is True
        off = await client.post(
            "/api/v1/system/kill-switch/deactivate",
            json={"reason": "test"},
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert off.status_code == 200


@pytest.mark.asyncio
async def test_paper_reset_requires_confirmation() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        bad = await client.post(
            "/api/v1/paper/reset",
            json={"confirm": "nope"},
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert bad.status_code == 400
        good = await client.post(
            "/api/v1/paper/reset",
            json={"confirm": "RESET_PAPER_ACCOUNT"},
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert good.status_code == 200
        assert good.json()["ok"] is True
