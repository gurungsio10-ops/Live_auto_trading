"""Phase 10: monitoring + alerts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.monitoring import (
    ConsoleAlertChannel,
    HealthRegistry,
    MonitoringService,
    WebhookAlertChannel,
)
from app.monitoring.health import SystemHealth


@pytest.mark.asyncio
async def test_readiness_and_alerts():
    console = ConsoleAlertChannel()
    webhook = WebhookAlertChannel(url=None)
    registry = HealthRegistry(
        db_healthy=False,
        market_data_fresh=False,
        websocket_connected=False,
        error_count=5,
    )
    svc = MonitoringService(registry=registry, channels=[console, webhook])
    health = await svc.check_and_alert()
    assert health.status == "degraded"
    events = {a["event"] for a in console.sent}
    assert "DB_UNAVAILABLE" in events
    assert "DATA_STALE" in events
    assert "REPEATED_EXCHANGE_ERRORS" in events
    assert webhook.sent


@pytest.mark.asyncio
async def test_readiness_ready_when_healthy():
    svc = MonitoringService(
        registry=HealthRegistry(
            db_healthy=True,
            redis_healthy=True,
            market_data_fresh=True,
            websocket_connected=False,  # optional in paper mode
            strategy_heartbeat_ok=True,
            order_engine_ok=True,
            risk_engine_ok=True,
        )
    )
    health = svc.readiness()
    assert health.status == "ready"
    assert health.trading_mode == "paper"
    assert health.kill_switch_enabled is False
    payload = health.to_dict()
    assert payload["status"] == "ready"
    assert payload["trading_mode"] == "paper"
    names = {c["name"] for c in payload["components"]}
    assert {"database", "redis", "market_data", "risk_engine", "kill_switch"} <= names


@pytest.mark.asyncio
async def test_kill_switch_triggers_alert(monkeypatch):
    monkeypatch.setenv("KILL_SWITCH_ENABLED", "true")
    get_settings.cache_clear()
    console = ConsoleAlertChannel()
    svc = MonitoringService(
        registry=HealthRegistry(),
        channels=[console],
    )
    # Force settings with kill switch without relying solely on env cache quirks
    health = SystemHealth(
        status="degraded",
        trading_mode="paper",
        kill_switch_enabled=True,
        components=[],
    )

    async def fake_readiness():
        return health

    svc.readiness = lambda: health  # type: ignore[method-assign]
    result = await svc.check_and_alert()
    assert result.kill_switch_enabled is True
    assert any(a["event"] == "KILL_SWITCH_ACTIVATED" for a in console.sent)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_redis_and_risk_alerts():
    console = ConsoleAlertChannel()
    svc = MonitoringService(
        registry=HealthRegistry(redis_healthy=False, risk_engine_ok=False),
        channels=[console],
    )
    await svc.check_and_alert()
    events = {a["event"] for a in console.sent}
    assert "REDIS_UNAVAILABLE" in events
    assert "RISK_HALT" in events


def test_api_health_endpoints_report_paper_mode():
    client = TestClient(app)
    root = client.get("/health")
    assert root.status_code == 200
    body = root.json()
    assert body["status"] == "ok"
    assert body["trading_mode"] == "paper"
    assert body["live_trading_enabled"] is False

    ready = client.get("/api/health/ready")
    assert ready.status_code == 200
    ready_body = ready.json()
    assert ready_body["trading_mode"] == "paper"
    assert "components" in ready_body
    assert ready_body["status"] in {"ready", "degraded"}


@pytest.mark.asyncio
async def test_manual_alert_fans_out_to_channels():
    console = ConsoleAlertChannel()
    webhook = WebhookAlertChannel(url="https://example.invalid/hook")
    svc = MonitoringService(channels=[console, webhook])
    await svc.alert("CUSTOM", "hello", {"x": 1})
    assert console.sent[-1]["event"] == "CUSTOM"
    assert webhook.sent[-1]["payload"] == {"x": 1}
    assert "ts" in webhook.sent[-1]
