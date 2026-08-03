"""Health/readiness probes and alerting interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.time import utc_now


@dataclass
class ComponentHealth:
    name: str
    healthy: bool
    detail: str = ""
    checked_at: datetime = field(default_factory=utc_now)


@dataclass
class SystemHealth:
    status: str
    trading_mode: str
    kill_switch_enabled: bool
    components: list[ComponentHealth]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "trading_mode": self.trading_mode,
            "kill_switch_enabled": self.kill_switch_enabled,
            "components": [
                {
                    "name": c.name,
                    "healthy": c.healthy,
                    "detail": c.detail,
                    "checked_at": c.checked_at.isoformat(),
                }
                for c in self.components
            ],
        }


class AlertChannel(Protocol):
    async def send(
        self, event: str, message: str, payload: dict[str, Any] | None = None
    ) -> None: ...


class ConsoleAlertChannel:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(
        self, event: str, message: str, payload: dict[str, Any] | None = None
    ) -> None:
        self.sent.append({"event": event, "message": message, "payload": payload or {}})
        print(f"[ALERT] {event}: {message}")


class WebhookAlertChannel:
    """Interface only — no real credentials required."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url
        self.sent: list[dict[str, Any]] = []

    async def send(
        self, event: str, message: str, payload: dict[str, Any] | None = None
    ) -> None:
        body = {
            "event": event,
            "message": message,
            "payload": payload or {},
            "ts": utc_now().isoformat(),
        }
        self.sent.append(body)
        # Intentionally does not perform HTTP unless url set and httpx used by caller later.


@dataclass
class HealthRegistry:
    db_healthy: bool = True
    redis_healthy: bool = True
    market_data_fresh: bool = True
    websocket_connected: bool = False
    strategy_heartbeat_ok: bool = True
    order_engine_ok: bool = True
    risk_engine_ok: bool = True
    error_count: int = 0
    trading_paused: bool = False
    last_market_data_at: datetime | None = None


class MonitoringService:
    def __init__(
        self,
        registry: HealthRegistry | None = None,
        channels: list[AlertChannel] | None = None,
    ) -> None:
        self.registry = registry or HealthRegistry()
        self.channels = channels or [ConsoleAlertChannel()]

    def readiness(self) -> SystemHealth:
        settings = get_settings()
        components = [
            ComponentHealth("database", self.registry.db_healthy),
            ComponentHealth("redis", self.registry.redis_healthy),
            ComponentHealth("market_data", self.registry.market_data_fresh),
            ComponentHealth("websocket", self.registry.websocket_connected),
            ComponentHealth("strategy", self.registry.strategy_heartbeat_ok),
            ComponentHealth("order_engine", self.registry.order_engine_ok),
            ComponentHealth("risk_engine", self.registry.risk_engine_ok),
            ComponentHealth(
                "kill_switch",
                not settings.kill_switch_enabled,
                detail="active" if settings.kill_switch_enabled else "inactive",
            ),
        ]
        healthy = all(c.healthy for c in components if c.name != "websocket")
        # websocket optional for paper REST mode
        status = "ready" if healthy and not settings.kill_switch_enabled else "degraded"
        return SystemHealth(
            status=status,
            trading_mode=settings.trading_mode,
            kill_switch_enabled=settings.kill_switch_enabled,
            components=components,
        )

    async def alert(
        self, event: str, message: str, payload: dict[str, Any] | None = None
    ) -> None:
        for channel in self.channels:
            await channel.send(event, message, payload)

    async def check_and_alert(self) -> SystemHealth:
        health = self.readiness()
        mapping = {
            "database": "DB_UNAVAILABLE",
            "redis": "REDIS_UNAVAILABLE",
            "market_data": "DATA_STALE",
            "websocket": "FEED_DISCONNECTED",
            "risk_engine": "RISK_HALT",
        }
        for comp in health.components:
            if not comp.healthy and comp.name in mapping:
                await self.alert(
                    mapping[comp.name],
                    f"{comp.name} unhealthy",
                    {"detail": comp.detail},
                )
        if health.kill_switch_enabled:
            await self.alert("KILL_SWITCH_ACTIVATED", "Kill switch is enabled")
        if self.registry.error_count >= 5:
            await self.alert(
                "REPEATED_EXCHANGE_ERRORS", f"error_count={self.registry.error_count}"
            )
        return health
