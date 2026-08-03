"""Live health probes for database, redis, exchange, websocket, engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.core.time import utc_now
from app.monitoring.health import ComponentHealth, HealthRegistry


@dataclass
class Diagnostics:
    checked_at: datetime = field(default_factory=utc_now)
    components: list[ComponentHealth] = field(default_factory=list)
    execution_latency_ms: float | None = None
    exchange_env: str = "paper"

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked_at": self.checked_at.isoformat(),
            "exchange_env": self.exchange_env,
            "execution_latency_ms": self.execution_latency_ms,
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


async def probe_database(database_url: str | None = None) -> ComponentHealth:
    settings = get_settings()
    url = database_url or settings.database_url
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return ComponentHealth("database", True, "ok")
    except Exception as exc:
        return ComponentHealth("database", False, type(exc).__name__)


async def probe_redis(redis_url: str | None = None) -> ComponentHealth:
    settings = get_settings()
    url = redis_url or settings.redis_url
    try:
        import redis.asyncio as redis

        client = redis.from_url(url, socket_connect_timeout=1)
        pong = await client.ping()
        await client.aclose()
        return ComponentHealth("redis", bool(pong), "pong" if pong else "no pong")
    except Exception as exc:
        # Redis is optional for paper; report unhealthy but non-fatal in readiness.
        return ComponentHealth("redis", False, type(exc).__name__)


def probe_from_registry(
    registry: HealthRegistry,
    *,
    execution_latency_ms: float | None = None,
    exchange_connected: bool = False,
    reconcile_healthy: bool = True,
) -> Diagnostics:
    settings = get_settings()
    components = [
        ComponentHealth("database", registry.db_healthy),
        ComponentHealth("redis", registry.redis_healthy),
        ComponentHealth(
            "exchange_api", exchange_connected or settings.exchange_env == "paper"
        ),
        ComponentHealth("websocket", registry.websocket_connected),
        ComponentHealth("strategy_engine", registry.strategy_heartbeat_ok),
        ComponentHealth("risk_engine", registry.risk_engine_ok),
        ComponentHealth("portfolio", reconcile_healthy),
        ComponentHealth("order_engine", registry.order_engine_ok),
        ComponentHealth(
            "market_data",
            registry.market_data_fresh,
            detail=(
                registry.last_market_data_at.isoformat()
                if registry.last_market_data_at
                else "no data"
            ),
        ),
    ]
    return Diagnostics(
        components=components,
        execution_latency_ms=execution_latency_ms,
        exchange_env=settings.exchange_env,
    )
