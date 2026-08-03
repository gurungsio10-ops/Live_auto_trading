"""Phase 10: monitoring + alerts."""

from __future__ import annotations

import pytest

from app.monitoring import ConsoleAlertChannel, HealthRegistry, MonitoringService, WebhookAlertChannel


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
