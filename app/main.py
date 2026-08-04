"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.mvp import router as mvp_router
from app.api.routes import router as api_router
from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.errors import AtlasError, ConfigurationError, LiveTradingDisabledError
from app.core.logging import configure_logging
from app.core.security import redact_settings
from app.services.paper_session import bootstrap_paper_runtime, get_paper_session


async def _probe_database() -> bool:
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.db.base import create_engine

        engine = create_engine()
        factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.assert_startup_safe()
    await bootstrap_paper_runtime()
    try:
        yield
    finally:
        # Graceful shutdown: dispose SQLAlchemy engines.
        from app.db import base as db_base

        try:
            await db_base.engine.dispose()
        except Exception:
            pass


settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.3.1",
    description=(
        "Project Atlas — personal cryptocurrency paper trading platform. "
        "AI is advisory only. Every order passes through the central risk engine. "
        "Live money trading is not enabled."
    ),
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api")
app.include_router(mvp_router, prefix="/api")
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
@app.get("/health/live")
async def health() -> dict[str, Any]:
    s = get_settings()
    session = get_paper_session()
    return {
        "status": "ok",
        "trading_mode": s.trading_mode,
        "runtime_mode": s.runtime_mode.value,
        "live_trading_enabled": s.live_trading_enabled,
        "kill_switch_enabled": session.kill_switch_enabled or s.kill_switch_enabled,
        "exchange_env": s.exchange_env,
    }


@app.get("/ready")
@app.get("/health/ready")
async def ready() -> dict[str, Any]:
    s = get_settings()
    # LIVE is never ready in this phase. PAPER and TESTNET may be ready.
    if s.runtime_mode.value == "LIVE" or s.trading_mode == "live":
        return {
            "status": "not_ready",
            "reason": "LIVE runtime is hard-blocked",
            "runtime_mode": s.runtime_mode.value,
            "database_ok": False,
        }
    db_ok = await _probe_database()
    if not db_ok:
        return {
            "status": "not_ready",
            "reason": "database probe failed",
            "runtime_mode": s.runtime_mode.value,
            "database_ok": False,
        }
    return {
        "status": "ready",
        "trading_mode": s.trading_mode,
        "runtime_mode": s.runtime_mode.value,
        "database_ok": True,
    }


@app.get("/config/safe")
async def safe_config() -> dict[str, Any]:
    payload = redact_settings(settings)
    payload["runtime_mode"] = get_settings().runtime_mode.value
    return payload
