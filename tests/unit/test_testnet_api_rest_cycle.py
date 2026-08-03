"""API: REST cycle path for use_sample_candles=false."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app
from app.services.testnet_runtime import reset_testnet_runtime


@pytest.fixture(autouse=True)
def _reset():
    reset_testnet_runtime()
    get_settings.cache_clear()
    yield
    reset_testnet_runtime()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_rest_cycle_requires_testnet_env(monkeypatch):
    monkeypatch.setenv("EXCHANGE_ENV", "paper")
    monkeypatch.setenv("TRADING_MODE", "paper")
    get_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/testnet/cycle/run",
            json={"symbol": "BTC/USDT", "use_sample_candles": False},
        )
    assert resp.status_code == 400
    assert "testnet" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rest_cycle_happy_path(monkeypatch):
    monkeypatch.setenv("EXCHANGE_ENV", "testnet")
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("EXCHANGE_API_KEY", "k" * 24)
    monkeypatch.setenv("EXCHANGE_API_SECRET", "s" * 24)
    get_settings.cache_clear()

    with patch(
        "app.services.testnet_runtime.TestnetRuntime.run_rest_cycle",
        new=AsyncMock(
            return_value={
                "accepted": True,
                "signal_direction": "hold",
                "order_id": None,
            }
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/testnet/cycle/run",
                json={
                    "symbol": "BTC/USDT",
                    "use_sample_candles": False,
                    "lookback": 60,
                },
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["simulated_testnet"] is False
    assert body["data_source"] == "rest_klines"
    assert body["cycle"]["accepted"] is True
