"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
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


async def _reconciliation_loop(stop: asyncio.Event) -> None:
    from app.services.reconciliation import run_paper_reconciliation

    settings = get_settings()
    while not stop.is_set():
        try:
            await run_paper_reconciliation()
        except Exception:
            pass
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=settings.reconciliation_interval_seconds
            )
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    from app.services.trading_scheduler import start_scheduler, stop_scheduler

    settings = get_settings()
    settings.assert_startup_safe()
    await bootstrap_paper_runtime()
    stop = asyncio.Event()
    recon_task: asyncio.Task[None] | None = None
    if settings.enable_reconciliation:
        recon_task = asyncio.create_task(
            _reconciliation_loop(stop), name="atlas-reconciliation"
        )
    start_scheduler()
    try:
        yield
    finally:
        stop.set()
        await stop_scheduler()
        if recon_task is not None:
            recon_task.cancel()
            try:
                await recon_task
            except asyncio.CancelledError:
                pass
        from app.db import base as db_base

        try:
            await db_base.engine.dispose()
        except Exception:
            pass


settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description=(
        "Project Atlas — personal cryptocurrency paper/testnet trading platform. "
        "AI is advisory only. Every order passes through the central risk engine. "
        "Live money trading is hard-blocked."
    ),
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api")
app.include_router(mvp_router, prefix="/api")
app.include_router(v1_router, prefix="/api/v1")
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
    from app.services.reconciliation import reconciliation_status
    from app.services.trading_scheduler import scheduler_status

    s = get_settings()
    session = get_paper_session()
    return {
        "status": "ok",
        "trading_mode": s.trading_mode,
        "runtime_mode": s.runtime_mode.value,
        "live_trading_enabled": s.live_trading_enabled,
        "kill_switch_enabled": session.kill_switch_enabled or s.kill_switch_enabled,
        "exchange_env": s.exchange_env,
        "scheduler": scheduler_status(),
        "reconciliation": reconciliation_status(),
        "banner": "PAPER TRADING — NO REAL FUNDS",
    }


@app.get("/ready")
@app.get("/health/ready")
async def ready() -> dict[str, Any]:
    from app.services.reconciliation import is_reconciliation_healthy

    s = get_settings()
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
        "reconciliation_healthy": is_reconciliation_healthy(),
    }


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Lightweight JSON metrics (Prometheus optional later)."""
    from app.services.paper_cycle import last_cycle_result
    from app.services.reconciliation import reconciliation_status
    from app.services.trading_scheduler import scheduler_status

    session = get_paper_session()
    cycle = last_cycle_result()
    return {
        "orders": len(session.orders()),
        "positions": len(session.positions()),
        "signals": len(session.signals()),
        "risk_events": len(session.risk_events()),
        "kill_switch_enabled": session.kill_switch_enabled,
        "scheduler": scheduler_status(),
        "reconciliation": reconciliation_status(),
        "last_cycle_signal": cycle.signal_direction if cycle else None,
        "live_orders_allowed": False,
    }


@app.get("/config/safe")
async def safe_config() -> dict[str, Any]:
    payload = redact_settings(settings)
    payload["runtime_mode"] = get_settings().runtime_mode.value
    return payload
