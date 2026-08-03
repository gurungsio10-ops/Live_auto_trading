"""Broader coverage for /api/v1/testnet/* endpoints."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("ADMIN_API_TOKEN", "test-admin-token")
os.environ.setdefault("TRADING_MODE", "paper")
os.environ.setdefault("EXCHANGE_ENV", "paper")

from app.core.config import get_settings
from app.main import app
from app.services.testnet_runtime import reset_testnet_runtime


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-admin-token")
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("EXCHANGE_ENV", "paper")
    get_settings.cache_clear()
    reset_testnet_runtime()
    yield
    reset_testnet_runtime()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_status_and_dashboard_without_runtime():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        status = await client.get("/api/v1/testnet/status")
        assert status.status_code == 200
        body = status.json()
        assert body["live_disabled"] is True
        assert body["runtime_active"] is False

        dash = await client.get("/api/v1/testnet/dashboard")
        assert dash.status_code == 200
        assert dash.json()["runtime_active"] is False

        diag = await client.get("/api/v1/testnet/diagnostics")
        assert diag.status_code == 200
        assert "database" in diag.json()


@pytest.mark.asyncio
async def test_sample_cycle_and_kill_switch():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cycle = await client.post(
            "/api/v1/testnet/cycle/run",
            json={"symbol": "BTC/USDT", "use_sample_candles": True},
        )
        assert cycle.status_code == 200
        body = cycle.json()
        assert body["simulated_testnet"] is True
        assert body["data_source"] == "sample_candles"
        assert "dashboard" in body

        denied = await client.post(
            "/api/v1/testnet/kill-switch", json={"enabled": True}
        )
        assert denied.status_code in {401, 503}

        ok = await client.post(
            "/api/v1/testnet/kill-switch",
            json={"enabled": True, "reason": "test"},
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert ok.status_code == 200
        assert ok.json()["kill_switch_enabled"] is True

        status = await client.get("/api/v1/testnet/status")
        assert status.json()["runtime_active"] is True


@pytest.mark.asyncio
async def test_runtime_start_paper_env():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/testnet/runtime/start",
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert res.status_code == 200
        assert res.json()["ok"] is True
        again = await client.post(
            "/api/v1/testnet/runtime/start",
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert again.json()["already_running"] is True


@pytest.mark.asyncio
async def test_rest_cycle_requires_credentials(monkeypatch):
    monkeypatch.setenv("EXCHANGE_ENV", "testnet")
    monkeypatch.delenv("EXCHANGE_API_KEY", raising=False)
    monkeypatch.delenv("EXCHANGE_API_SECRET", raising=False)
    get_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/testnet/cycle/run",
            json={"use_sample_candles": False},
        )
    assert resp.status_code == 400
    assert "credential" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_diagnostics_with_runtime():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/testnet/cycle/run",
            json={"use_sample_candles": True},
        )
        with (
            patch(
                "app.api.testnet.probe_database",
                new=AsyncMock(
                    return_value=type("P", (), {"healthy": True, "detail": "ok"})()
                ),
            ),
            patch(
                "app.api.testnet.probe_redis",
                new=AsyncMock(
                    return_value=type("P", (), {"healthy": True, "detail": "ok"})()
                ),
            ),
        ):
            diag = await client.get("/api/v1/testnet/diagnostics")
        assert diag.status_code == 200
        payload = diag.json()
        assert payload["database"]["healthy"] is True
