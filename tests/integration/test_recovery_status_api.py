"""Recovery status API shape for operations dashboard."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["ADMIN_API_TOKEN"] = "test-admin-token"
os.environ.setdefault("TRADING_MODE", "paper")

from app.core.config import get_settings
from app.main import app
from app.services import paper_cycle
from app.services.paper_session import reset_paper_session


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    paper_cycle.reset_cycle_state()
    reset_paper_session()
    yield
    paper_cycle.reset_cycle_state()
    reset_paper_session()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_recovery_status_includes_ops_fields() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/recovery/status")
        assert r.status_code == 200
        body = r.json()
        recovery = body.get("recovery", body)
        for key in (
            "runtime_mode",
            "trading_mode",
            "kill_switch_enabled",
            "trading_enabled",
            "trading_paused",
            "last_hydrated_at",
            "persistence_status",
            "database_status",
            "scheduler",
            "market_data_stale",
            "portfolio",
            "risk",
            "reconciliation",
        ):
            assert key in recovery, f"missing {key}"
        assert "open_positions" in recovery["portfolio"]
        assert "open_orders" in recovery["portfolio"]
