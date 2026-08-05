"""Root ops endpoints on FastAPI app (health, ready, metrics, market)."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["ADMIN_API_TOKEN"] = "test-admin-token"
os.environ.setdefault("TRADING_MODE", "paper")
os.environ.setdefault("ENABLE_OPS_SSE", "false")

from app.core.config import get_settings
from app.core.errors import AtlasError, ConfigurationError, LiveTradingDisabledError
from app.main import app
from app.services.paper_session import reset_paper_session
from app.services.reconciliation import clear_reconciliation_halt


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    reset_paper_session()
    clear_reconciliation_halt()
    yield
    reset_paper_session()
    clear_reconciliation_halt()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_root_health_ready_metrics_config():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h = await client.get("/health")
        assert h.status_code == 200
        body = h.json()
        assert body["status"] == "ok"
        assert "PAPER" in body["banner"]
        assert "database" in body
        assert "ok" in body["database"]
        assert "risk_flag" in body["database"]

        r = await client.get("/ready")
        assert r.status_code == 200
        assert r.json()["status"] in {"ready", "not_ready"}

        m = await client.get("/metrics")
        assert m.status_code == 200
        assert m.json()["live_orders_allowed"] is False

        c = await client.get("/config/safe")
        assert c.status_code == 200
        body = c.json()
        assert "runtime_mode" in body

        ms = await client.get("/api/market/status")
        assert ms.status_code == 200
        assert ms.json()["websocket_observation_only"] is True

        pm = await client.get("/api/portfolio/manager")
        assert pm.status_code == 200

        adv = await client.get("/api/market/derivatives/advisory")
        assert adv.status_code == 200
        assert adv.json()["advisory"] is True

        sse = await client.get("/ops/stream")
        assert sse.status_code == 503


@pytest.mark.asyncio
async def test_exception_handlers():
    transport = ASGITransport(app=app)

    @app.get("/_test/live-disabled")
    async def _live():
        raise LiveTradingDisabledError("blocked")

    @app.get("/_test/config-error")
    async def _cfg():
        raise ConfigurationError("bad config")

    @app.get("/_test/atlas-error")
    async def _atlas():
        raise AtlasError("nope")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/_test/live-disabled")).status_code == 501
        assert (await client.get("/_test/config-error")).status_code == 500
        assert (await client.get("/_test/atlas-error")).status_code == 400
