"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.routes import router as api_router
from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.errors import AtlasError, ConfigurationError, LiveTradingDisabledError
from app.core.logging import configure_logging
from app.core.security import redact_settings
from app.monitoring.metrics import build_system_health, render_prometheus
from app.services.paper_persistence import hydrate_paper_session
from app.services.paper_session import get_paper_session
from app.services.scheduler_service import ensure_default_job, start_worker, stop_worker


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.assert_startup_safe()
    # Restore durable paper state (no-op seed on first boot).
    try:
        await hydrate_paper_session(get_paper_session())
    except Exception:
        # Fresh SQLite without migrations should not block API boot in tests.
        pass
    try:
        await ensure_default_job()
    except Exception:
        pass
    if settings.scheduler_enabled and settings.trading_mode == "paper":
        await start_worker()
    try:
        yield
    finally:
        await stop_worker()


settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Project Atlas — personal cryptocurrency paper trading platform. "
        "AI is advisory only. Every order passes through the central risk engine. "
        "Live money trading is not enabled. Simulated results do not guarantee "
        "future performance."
    ),
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api")
app.include_router(v1_router, prefix="/api/v1")
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
    """Liveness — process is up."""
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled,
        "kill_switch_enabled": get_paper_session().kill_switch_enabled
        or settings.kill_switch_enabled,
        "exchange_env": settings.exchange_env,
    }


@app.get("/ready")
async def ready() -> dict[str, Any]:
    """Readiness — paper mode and database reachable."""
    from app.monitoring.metrics import probe_database

    if settings.trading_mode != "paper":
        return {"status": "not_ready", "reason": "trading_mode is not paper"}
    db = await probe_database()
    if not db["ok"]:
        return {"status": "not_ready", "reason": "database_unreachable"}
    return {"status": "ready", "trading_mode": settings.trading_mode, "database": db}


@app.get("/config/safe")
async def safe_config() -> dict[str, Any]:
    """Return redacted settings suitable for debugging."""
    return redact_settings(settings)


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus text exposition (no secrets)."""
    return PlainTextResponse(
        render_prometheus(), media_type="text/plain; version=0.0.4"
    )


@app.get("/system/health")
async def system_health() -> dict[str, Any]:
    return await build_system_health()
