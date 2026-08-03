"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.routes import router as api_router
from app.api.testnet import router as testnet_router
from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.errors import AtlasError, ConfigurationError, LiveTradingDisabledError
from app.core.logging import configure_logging
from app.core.security import redact_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.assert_startup_safe()
    yield


settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Project Atlas — personal cryptocurrency paper trading platform. "
        "AI is advisory only. Every order passes through the central risk engine. "
        "Live money trading is not enabled."
    ),
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api")
app.include_router(v1_router, prefix="/api/v1")
app.include_router(testnet_router, prefix="/api/v1")
# Root-level endpoints matching the Next.js proxy contract.
app.include_router(auth_router)
app.include_router(dashboard_router)


@app.exception_handler(LiveTradingDisabledError)
async def live_disabled_handler(
    _request: Request, exc: LiveTradingDisabledError
) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": str(exc)})


@app.exception_handler(ConfigurationError)
async def config_error_handler(
    _request: Request, exc: ConfigurationError
) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(AtlasError)
async def atlas_error_handler(_request: Request, exc: AtlasError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled,
        "kill_switch_enabled": settings.kill_switch_enabled,
        "exchange_env": settings.exchange_env,
    }


@app.get("/ready")
async def ready() -> dict[str, Any]:
    if settings.trading_mode != "paper":
        return {"status": "not_ready", "reason": "trading_mode is not paper"}
    return {"status": "ready", "trading_mode": settings.trading_mode}


@app.get("/config/safe")
async def safe_config() -> dict[str, Any]:
    """Return redacted settings suitable for debugging."""
    return redact_settings(settings)
