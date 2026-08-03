"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import redact_settings

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled,
        "kill_switch_enabled": settings.kill_switch_enabled,
        "exchange_env": settings.exchange_env,
    }


@app.get("/config/safe")
async def safe_config() -> dict:
    """Return redacted settings suitable for debugging."""
    return redact_settings(settings)
